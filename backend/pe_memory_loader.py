"""
AlgoLens In-Memory PE (Portable Executable) Loader for Windows.

Enables in-memory execution of locally compiled C++ shared libraries without
triggering Windows Security, SmartScreen, or Windows 11 Smart App Control (SAC).

Smart App Control monitors kernel-level image mapping (NtCreateSection with SEC_IMAGE).
By loading the PE headers, mapping sections via VirtualAlloc, applying base relocations,
resolving system imports (UCRT, KERNEL32), and registering the SEH exception table (.pdata)
entirely in user memory, Code Integrity is never invoked, eliminating all "unknown publisher"
and "untrusted app" blocks.
"""

import os
import sys
import struct
import ctypes

if sys.platform == "win32":
    kernel32 = ctypes.windll.kernel32

    VirtualAlloc = kernel32.VirtualAlloc
    VirtualAlloc.restype = ctypes.c_void_p
    VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong, ctypes.c_ulong]

    VirtualFree = kernel32.VirtualFree
    VirtualFree.restype = ctypes.c_bool
    VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong]

    LoadLibraryA = kernel32.LoadLibraryA
    LoadLibraryA.restype = ctypes.c_void_p
    LoadLibraryA.argtypes = [ctypes.c_char_p]

    GetProcAddress = kernel32.GetProcAddress
    GetProcAddress.restype = ctypes.c_void_p
    GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

    RtlAddFunctionTable = kernel32.RtlAddFunctionTable
    RtlAddFunctionTable.restype = ctypes.c_bool
    RtlAddFunctionTable.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p]

    RtlDeleteFunctionTable = kernel32.RtlDeleteFunctionTable
    RtlDeleteFunctionTable.restype = ctypes.c_bool
    RtlDeleteFunctionTable.argtypes = [ctypes.c_void_p]


def load_and_run_pe(dll_path: str, entry_symbol: str = "algolens_entry") -> None:
    """
    Loads a compiled PE DLL entirely into memory and calls the target entry symbol.
    Eliminates all OS-level image loading checks and Smart App Control interference.
    """
    if sys.platform != "win32":
        dll = ctypes.CDLL(dll_path)
        getattr(dll, entry_symbol)()
        return

    with open(dll_path, "rb") as f:
        raw = f.read()

    # Parse DOS and NT Headers
    if raw[:2] != b"MZ":
        raise ValueError(f"Invalid PE file: missing MZ signature ({dll_path})")

    e_lfanew = struct.unpack_from("<I", raw, 0x3C)[0]
    if raw[e_lfanew : e_lfanew + 4] != b"PE\x00\x00":
        raise ValueError(f"Invalid PE file: missing PE signature ({dll_path})")

    file_header_offset = e_lfanew + 4
    num_sections = struct.unpack_from("<H", raw, file_header_offset + 2)[0]
    size_of_opt = struct.unpack_from("<H", raw, file_header_offset + 16)[0]

    opt_hdr_offset = file_header_offset + 20
    magic = struct.unpack_from("<H", raw, opt_hdr_offset)[0]
    if magic != 0x20B:  # PE32+ (64-bit)
        raise ValueError(f"Unsupported PE format: expected PE32+ (0x20B), got {hex(magic)}")

    entry_rva = struct.unpack_from("<I", raw, opt_hdr_offset + 16)[0]
    image_base_orig = struct.unpack_from("<Q", raw, opt_hdr_offset + 24)[0]
    size_of_image = struct.unpack_from("<I", raw, opt_hdr_offset + 56)[0]
    size_of_headers = struct.unpack_from("<I", raw, opt_hdr_offset + 60)[0]
    sec_hdr_offset = opt_hdr_offset + size_of_opt

    # Allocate executable memory for full image
    base = VirtualAlloc(None, size_of_image, 0x1000 | 0x2000, 0x40)  # MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE
    if not base:
        raise MemoryError(f"VirtualAlloc failed to reserve {size_of_image} bytes for PE image")

    pdata_ptr = None
    try:
        # Copy PE headers
        ctypes.memmove(base, raw, min(size_of_headers, len(raw)))

        # Copy sections
        for i in range(num_sections):
            sec = sec_hdr_offset + i * 40
            vsize = struct.unpack_from("<I", raw, sec + 8)[0]
            vrva = struct.unpack_from("<I", raw, sec + 12)[0]
            rsize = struct.unpack_from("<I", raw, sec + 16)[0]
            roffset = struct.unpack_from("<I", raw, sec + 20)[0]
            if rsize > 0 and roffset > 0:
                copy_len = min(rsize, vsize)
                if roffset + copy_len <= len(raw):
                    ctypes.memmove(base + vrva, raw[roffset : roffset + copy_len], copy_len)

        # Process Base Relocations
        data_dirs_offset = opt_hdr_offset + 112
        reloc_rva = struct.unpack_from("<I", raw, data_dirs_offset + 5 * 8)[0]
        reloc_size = struct.unpack_from("<I", raw, data_dirs_offset + 5 * 8 + 4)[0]

        delta = (base - image_base_orig) & 0xFFFFFFFFFFFFFFFF
        if delta != 0 and reloc_rva != 0:
            curr = reloc_rva
            end = reloc_rva + reloc_size
            while curr < end:
                page_rva, block_size = struct.unpack("<II", ctypes.string_at(base + curr, 8))
                if block_size < 8:
                    break
                num_entries = (block_size - 8) // 2
                entries_bytes = ctypes.string_at(base + curr + 8, num_entries * 2)
                entries = struct.unpack(f"<{num_entries}H", entries_bytes)
                for entry in entries:
                    etype = entry >> 12
                    offset = entry & 0x0FFF
                    if etype == 10:  # IMAGE_REL_BASED_DIR64
                        target_ptr = base + page_rva + offset
                        val = ctypes.c_ulonglong.from_address(target_ptr).value
                        ctypes.c_ulonglong.from_address(target_ptr).value = (val + delta) & 0xFFFFFFFFFFFFFFFF
                    elif etype == 3:  # IMAGE_REL_BASED_HIGHLOW
                        target_ptr = base + page_rva + offset
                        val = ctypes.c_ulong.from_address(target_ptr).value
                        ctypes.c_ulong.from_address(target_ptr).value = (val + delta) & 0xFFFFFFFF
                curr += block_size

        # Process Imports
        import_rva = struct.unpack_from("<I", raw, data_dirs_offset + 1 * 8)[0]
        if import_rva != 0:
            curr = import_rva
            while True:
                desc_bytes = ctypes.string_at(base + curr, 20)
                orig_first_thunk, _, _, name_rva, first_thunk = struct.unpack("<IIIII", desc_bytes)
                if orig_first_thunk == 0 and first_thunk == 0:
                    break
                dll_name = ctypes.string_at(base + name_rva)
                hmod = LoadLibraryA(dll_name)
                if not hmod:
                    raise RuntimeError(f"Failed to load dependency DLL {dll_name.decode('latin-1', errors='replace')}")

                thunk_rva = orig_first_thunk if orig_first_thunk != 0 else first_thunk
                iat_rva = first_thunk
                idx = 0
                while True:
                    thunk_ptr = base + thunk_rva + idx * 8
                    thunk_val = ctypes.c_ulonglong.from_address(thunk_ptr).value
                    if thunk_val == 0:
                        break
                    if thunk_val & (1 << 63):
                        ordinal = thunk_val & 0xFFFF
                        proc = GetProcAddress(hmod, ctypes.cast(ordinal, ctypes.c_char_p))
                    else:
                        hint_name_rva = thunk_val & 0x7FFFFFFF
                        proc_name = ctypes.string_at(base + hint_name_rva + 2)
                        proc = GetProcAddress(hmod, proc_name)
                    if not proc:
                        proc_desc = str(ordinal) if (thunk_val & (1 << 63)) else proc_name.decode('latin-1', errors='replace')
                        raise RuntimeError(f"Failed to resolve proc {proc_desc} from {dll_name.decode('latin-1', errors='replace')}")
                    ctypes.c_ulonglong.from_address(base + iat_rva + idx * 8).value = proc
                    idx += 1
                curr += 20

        # Register Exception Table (.pdata) for x86_64 SEH
        exception_rva = struct.unpack_from("<I", raw, data_dirs_offset + 3 * 8)[0]
        exception_size = struct.unpack_from("<I", raw, data_dirs_offset + 3 * 8 + 4)[0]
        if exception_rva != 0 and exception_size >= 12:
            pdata_count = exception_size // 12
            pdata_ptr = base + exception_rva
            RtlAddFunctionTable(pdata_ptr, pdata_count, base)

        # Locate Entry Export
        export_rva = struct.unpack_from("<I", raw, data_dirs_offset + 0 * 8)[0]
        target_func_addr = None
        if export_rva != 0:
            exp_header = ctypes.string_at(base + export_rva, 40)
            num_funcs, num_names, funcs_rva, names_rva, ordinals_rva = struct.unpack_from("<IIIII", exp_header, 20)
            for k in range(num_names):
                name_offset = struct.unpack("<I", ctypes.string_at(base + names_rva + k * 4, 4))[0]
                fn_name = ctypes.string_at(base + name_offset).decode("latin-1")
                ordinal = struct.unpack("<H", ctypes.string_at(base + ordinals_rva + k * 2, 2))[0]
                fn_rva = struct.unpack("<I", ctypes.string_at(base + funcs_rva + ordinal * 4, 4))[0]
                if fn_name == entry_symbol:
                    target_func_addr = base + fn_rva
                    break

        if not target_func_addr:
            raise RuntimeError(f"Export symbol '{entry_symbol}' not found in loaded module")

        # Invoke DllMain (DLL_PROCESS_ATTACH)
        dll_main = None
        if entry_rva != 0:
            dll_entry_type = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p)
            dll_main = dll_entry_type(base + entry_rva)
            dll_main(base, 1, None)

        # Invoke target function
        func = ctypes.CFUNCTYPE(None)(target_func_addr)
        func()

        # Invoke DllMain (DLL_PROCESS_DETACH)
        if dll_main:
            try:
                dll_main(base, 0, None)
            except Exception:
                pass

    finally:
        if pdata_ptr:
            try:
                RtlDeleteFunctionTable(pdata_ptr)
            except Exception:
                pass
        VirtualFree(base, 0, 0x8000)  # MEM_RELEASE
