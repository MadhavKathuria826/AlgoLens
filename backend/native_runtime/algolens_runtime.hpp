#pragma once
/**
 * AlgoLens Native C++ Runtime Instrumentation Header (Milestone 4)
 * 
 * Provides:
 * 1. Native ObjectRegistry mapping physical memory addresses to synthetic AlgoLens Object IDs (obj_X).
 * 2. Dynamic memory allocation & deallocation tracking (OBJECT_ALLOCATE / OBJECT_DEALLOCATE).
 * 3. Dangling pointer detection and pointer aliasing.
 * 4. Struct/Class field mutation tracking (OBJECT_MUTATE).
 * 5. Pointer dereference mutation tracking.
 * 6. Standard library container semantic instrumentation (vector, stack, queue, map, unordered_map).
 * 7. AlgoLens Event Protocol v2.1 emission via [ALGOLENS_EVENT] stdout transport.
 */

#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <stack>
#include <queue>
#include <map>
#include <unordered_map>
#include <chrono>
#include <iomanip>
#include <cstdint>
#include <type_traits>

namespace algolens {

// Forward declarations
class ObjectRegistry;
class Runtime;

// --- JSON Helpers ---
inline std::string escape_json(const std::string& s) {
    std::ostringstream o;
    for (char c : s) {
        if (c == '"') o << "\\\"";
        else if (c == '\\') o << "\\\\";
        else if (c == '\b') o << "\\b";
        else if (c == '\f') o << "\\f";
        else if (c == '\n') o << "\\n";
        else if (c == '\r') o << "\\r";
        else if (c == '\t') o << "\\t";
        else if ('\x00' <= c && c <= '\x1f') {
            o << "\\u" << std::hex << std::setw(4) << std::setfill('0') << (int)c;
        } else {
            o << c;
        }
    }
    return o.str();
}

// --- Object Registry & Entry ---
struct ObjectEntry {
    std::string object_id;
    uintptr_t native_address = 0;
    std::string type_name;
    size_t size_bytes = 0;
    int allocated_line = 0;
    int creation_seq = 0;
    bool alive = false;
    std::unordered_map<std::string, std::string> fields; // field_name -> serialized JSON
};

class ObjectRegistry {
public:
    static ObjectRegistry& instance() {
        static ObjectRegistry inst;
        return inst;
    }

    int object_counter = 0;
    std::unordered_map<uintptr_t, std::string> active_addr_to_id;
    std::unordered_map<uintptr_t, std::string> dead_addr_to_last_id;
    std::unordered_map<std::string, ObjectEntry> registry;

    std::string register_allocation(uintptr_t addr, const std::string& type_name, size_t size_bytes, int line) {
        if (!addr) return "";

        std::string obj_id = "obj_" + std::to_string(object_counter++);
        active_addr_to_id[addr] = obj_id;
        dead_addr_to_last_id.erase(addr); // Pointer reuse: clean any old dead record for this address

        ObjectEntry entry;
        entry.object_id = obj_id;
        entry.native_address = addr;
        entry.type_name = type_name;
        entry.size_bytes = size_bytes;
        entry.allocated_line = line;
        entry.creation_seq = object_counter;
        entry.alive = true;

        registry[obj_id] = entry;
        return obj_id;
    }

    std::string get_or_register_address(uintptr_t addr, const std::string& fallback_type = "Object") {
        if (!addr) return "";
        auto it = active_addr_to_id.find(addr);
        if (it != active_addr_to_id.end()) {
            return it->second;
        }
        return register_allocation(addr, fallback_type, 0, 0);
    }

    std::string get_ref_json(uintptr_t addr) {
        if (!addr) {
            return "{\"kind\":\"null_ref\"}";
        }
        auto it = active_addr_to_id.find(addr);
        if (it != active_addr_to_id.end()) {
            return "{\"kind\":\"object_ref\",\"object_id\":\"" + it->second + "\"}";
        }
        auto dead_it = dead_addr_to_last_id.find(addr);
        if (dead_it != dead_addr_to_last_id.end()) {
            return "{\"kind\":\"dangling_ref\",\"last_known_object_id\":\"" + dead_it->second + "\"}";
        }
        // Unknown pointer registered on-the-fly
        std::string new_id = register_allocation(addr, "Object", 0, 0);
        return "{\"kind\":\"object_ref\",\"object_id\":\"" + new_id + "\"}";
    }

    bool deallocate(uintptr_t addr, std::string& out_obj_id, std::string& out_type, std::string& out_old_fields_json) {
        if (!addr) return false;
        auto it = active_addr_to_id.find(addr);
        if (it == active_addr_to_id.end()) {
            return false; // Unknown or double delete
        }
        out_obj_id = it->second;
        active_addr_to_id.erase(it);
        dead_addr_to_last_id[addr] = out_obj_id;

        auto reg_it = registry.find(out_obj_id);
        if (reg_it != registry.end()) {
            reg_it->second.alive = false;
            out_type = reg_it->second.type_name;
            
            std::ostringstream ss;
            ss << "{";
            bool first = true;
            for (const auto& pair : reg_it->second.fields) {
                if (!first) ss << ",";
                ss << "\"" << escape_json(pair.first) << "\":" << pair.second;
                first = false;
            }
            ss << "}";
            out_old_fields_json = ss.str();
        } else {
            out_type = "Object";
            out_old_fields_json = "{}";
        }
        return true;
    }
};

// Universal value serializer overloads
inline std::string value_to_json(bool v) {
    return std::string("{\"kind\":\"primitive\",\"type_name\":\"bool\",\"value\":") + (v ? "true" : "false") + "}";
}

inline std::string value_to_json(char v) {
    std::string s(1, v);
    return "{\"kind\":\"primitive\",\"type_name\":\"char\",\"value\":\"" + escape_json(s) + "\"}";
}

inline std::string value_to_json(int v) {
    return "{\"kind\":\"primitive\",\"type_name\":\"int\",\"value\":" + std::to_string(v) + "}";
}

inline std::string value_to_json(short v) {
    return "{\"kind\":\"primitive\",\"type_name\":\"short\",\"value\":" + std::to_string(v) + "}";
}

inline std::string value_to_json(long v) {
    return "{\"kind\":\"primitive\",\"type_name\":\"int\",\"value\":" + std::to_string(v) + "}";
}

inline std::string value_to_json(long long v) {
    return "{\"kind\":\"primitive\",\"type_name\":\"int\",\"value\":" + std::to_string(v) + "}";
}

inline std::string value_to_json(unsigned int v) {
    return "{\"kind\":\"primitive\",\"type_name\":\"int\",\"value\":" + std::to_string(v) + "}";
}

inline std::string value_to_json(unsigned long v) {
    return "{\"kind\":\"primitive\",\"type_name\":\"int\",\"value\":" + std::to_string(v) + "}";
}

inline std::string value_to_json(unsigned long long v) {
    return "{\"kind\":\"primitive\",\"type_name\":\"int\",\"value\":" + std::to_string(v) + "}";
}

inline std::string value_to_json(float v) {
    std::ostringstream ss;
    ss << std::setprecision(6) << v;
    return "{\"kind\":\"primitive\",\"type_name\":\"float\",\"value\":" + ss.str() + "}";
}

inline std::string value_to_json(double v) {
    std::ostringstream ss;
    ss << std::setprecision(8) << v;
    return "{\"kind\":\"primitive\",\"type_name\":\"float\",\"value\":" + ss.str() + "}";
}

inline std::string value_to_json(const std::string& v) {
    return "{\"kind\":\"primitive\",\"type_name\":\"string\",\"value\":\"" + escape_json(v) + "\"}";
}

inline std::string value_to_json(const char* v) {
    if (!v) return "{\"kind\":\"null_ref\"}";
    return "{\"kind\":\"primitive\",\"type_name\":\"string\",\"value\":\"" + escape_json(std::string(v)) + "\"}";
}

inline std::string value_to_json(std::nullptr_t) {
    return "{\"kind\":\"null_ref\"}";
}

template <typename T>
typename std::enable_if<std::is_pointer<T>::value, std::string>::type
value_to_json(T ptr) {
    if (!ptr) {
        return "{\"kind\":\"null_ref\"}";
    }
    return ObjectRegistry::instance().get_ref_json(reinterpret_cast<uintptr_t>(ptr));
}

// Fallback for unspecialized types
template <typename T>
typename std::enable_if<!std::is_pointer<T>::value && !std::is_arithmetic<T>::value, std::string>::type
value_to_json(const T& obj) {
    uintptr_t addr = reinterpret_cast<uintptr_t>(&obj);
    auto it = ObjectRegistry::instance().active_addr_to_id.find(addr);
    if (it != ObjectRegistry::instance().active_addr_to_id.end()) {
        return "{\"kind\":\"object_ref\",\"object_id\":\"" + it->second + "\"}";
    }
    return "{\"kind\":\"primitive\",\"type_name\":\"unknown\",\"value\":\"<object>\"}";
}


// --- Runtime State Singleton ---
class Runtime {
public:
    static Runtime& instance() {
        static Runtime inst;
        return inst;
    }

    int seq = 0;
    int current_line = 0;
    int last_emitted_line = 0;
    int frame_counter = 0;
    int scope_counter = 0;
    int binding_counter = 0;

    std::vector<std::string> frame_stack;
    std::vector<std::string> scope_stack;
    std::unordered_map<std::string, std::string> var_binding_ids;
    std::unordered_map<std::string, std::string> var_values;  // name -> serialized json

    struct VarAddrInfo {
        std::string name;
        std::string binding_id;
        std::string frame_id;
    };

    std::unordered_map<uintptr_t, VarAddrInfo> active_var_addrs;
    std::unordered_map<std::string, std::string> ref_target_names; // ref_name -> target_var_name
    bool initialized = false;

    Runtime() {
        init();
    }

    void init() {
        if (!initialized) {
            frame_stack.push_back("frame_0");
            scope_stack.push_back("scope_0");
            initialized = true;
        }
    }

    std::string current_frame_id() const {
        return frame_stack.empty() ? "frame_0" : frame_stack.back();
    }

    std::string current_scope_id() const {
        return scope_stack.empty() ? "scope_0" : scope_stack.back();
    }

    std::string get_or_create_binding_id(const std::string& name) {
        auto it = var_binding_ids.find(name);
        if (it != var_binding_ids.end()) {
            return it->second;
        }
        std::string bid = "binding_" + std::to_string(binding_counter++);
        var_binding_ids[name] = bid;
        return bid;
    }

    void emit_raw_event(const std::string& event_type, int line, const std::string& payload_json) {
        current_line = line;
        int prev_l = last_emitted_line;

        std::cout << "[ALGOLENS_EVENT] {"
                  << "\"seq\":" << seq++
                  << ",\"line\":" << line
                  << ",\"prev_line\":" << prev_l
                  << ",\"event_type\":\"" << event_type << "\""
                  << ",\"frame_id\":\"" << current_frame_id() << "\""
                  << ",\"scope_id\":\"" << current_scope_id() << "\""
                  << ",\"payload\":" << payload_json
                  << ",\"debug_meta\":null"
                  << ",\"ts\":null"
                  << "}\n";
        std::cout.flush();
        last_emitted_line = current_line;
    }

    // --- Core Hooks ---

    void on_prog_start(const char* entry_func, int line) {
        std::string payload = "{\"entry_function\":\"" + escape_json(entry_func) + "\",\"args\":{}}";
        emit_raw_event("PROG_START", line, payload);
    }

    void on_step_line(int line) {
        std::string payload = "{\"line\":" + std::to_string(line) + "}";
        emit_raw_event("STEP_LINE", line, payload);
    }

    void on_frame_push(const char* func_name, int line) {
        std::string fid = "frame_" + std::to_string(++frame_counter);
        std::string sid = "scope_" + std::to_string(++scope_counter);
        std::string parent_id = current_frame_id();
        frame_stack.push_back(fid);
        scope_stack.push_back(sid);

        std::string payload = "{\"func_name\":\"" + escape_json(func_name) + "\","
                            + "\"frame_id\":\"" + fid + "\","
                            + "\"parent_frame_id\":\"" + parent_id + "\","
                            + "\"args\":{}}";
        emit_raw_event("FRAME_PUSH", line, payload);
    }

    template <typename T>
    void on_frame_pop(int line, const T& ret_val) {
        std::string ret_json = value_to_json(ret_val);
        std::string payload = "{\"return_value\":" + ret_json + "}";
        emit_raw_event("FRAME_POP", line, payload);
        std::string popped = current_frame_id();
        if (frame_stack.size() > 1) frame_stack.pop_back();
        if (scope_stack.size() > 1) scope_stack.pop_back();

        for (auto it = active_var_addrs.begin(); it != active_var_addrs.end(); ) {
            if (it->second.frame_id == popped) {
                ref_target_names.erase(it->second.name);
                it = active_var_addrs.erase(it);
            } else {
                ++it;
            }
        }
    }

    void on_frame_pop_void(int line) {
        std::string payload = "{\"return_value\":null}";
        emit_raw_event("FRAME_POP", line, payload);
        std::string popped = current_frame_id();
        if (frame_stack.size() > 1) frame_stack.pop_back();
        if (scope_stack.size() > 1) scope_stack.pop_back();

        for (auto it = active_var_addrs.begin(); it != active_var_addrs.end(); ) {
            if (it->second.frame_id == popped) {
                ref_target_names.erase(it->second.name);
                it = active_var_addrs.erase(it);
            } else {
                ++it;
            }
        }
    }

    void on_scope_enter(const char* kind, int line) {
        std::string sid = "scope_" + std::to_string(++scope_counter);
        scope_stack.push_back(sid);
        std::string payload = "{\"kind\":\"" + escape_json(kind) + "\"}";
        emit_raw_event("SCOPE_ENTER", line, payload);
    }

    void on_scope_exit(int line) {
        std::string payload = "{}";
        emit_raw_event("SCOPE_EXIT", line, payload);
        if (scope_stack.size() > 1) {
            scope_stack.pop_back();
        }
    }

    template <typename T>
    void on_var_declare(const char* name, const char* type_str, const T& val, int line) {
        std::string bid = get_or_create_binding_id(name);
        uintptr_t addr = reinterpret_cast<uintptr_t>(&val);

        // Check if this address already belongs to an active variable (C++ reference)
        auto it_addr = active_var_addrs.find(addr);
        if (it_addr != active_var_addrs.end() && it_addr->second.name != name) {
            std::string target_name = it_addr->second.name;
            std::string target_bid = it_addr->second.binding_id;
            ref_target_names[name] = target_name;

            std::string val_json = "{\"kind\":\"reference\",\"target_name\":\"" + escape_json(target_name) + "\",\"target_binding_id\":\"" + target_bid + "\"}";
            var_values[name] = val_json;

            std::string payload = "{\"binding_id\":\"" + bid + "\","
                                + "\"name\":\"" + escape_json(name) + "\","
                                + "\"type_decl\":\"" + escape_json(type_str) + "\","
                                + "\"value\":" + val_json + "}";
            emit_raw_event("VAR_DECLARE", line, payload);
            return;
        }

        // Fresh variable
        active_var_addrs[addr] = {name, bid, current_frame_id()};
        std::string val_json = value_to_json(val);
        var_values[name] = val_json;

        std::string payload = "{\"binding_id\":\"" + bid + "\","
                            + "\"name\":\"" + escape_json(name) + "\","
                            + "\"type_decl\":\"" + escape_json(type_str) + "\","
                            + "\"value\":" + val_json + "}";
        emit_raw_event("VAR_DECLARE", line, payload);
    }

    template <typename T>
    void on_var_write(const char* name, const T& new_val, int line) {
        std::string target_name = name;
        auto it_ref = ref_target_names.find(name);
        if (it_ref != ref_target_names.end()) {
            target_name = it_ref->second;
        }

        std::string new_val_json = value_to_json(new_val);
        
        if (target_name != name) {
            std::string target_bid = get_or_create_binding_id(target_name);
            auto it_old = var_values.find(target_name);
            std::string old_val_json = (it_old != var_values.end()) ? it_old->second : "{\"kind\":\"uninitialized\"}";
            var_values[target_name] = new_val_json;

            std::string payload = "{\"binding_id\":\"" + target_bid + "\","
                                + "\"name\":\"" + escape_json(target_name) + "\","
                                + "\"old_value\":" + old_val_json + ","
                                + "\"new_value\":" + new_val_json + "}";
            emit_raw_event("VAR_WRITE", line, payload);
        }

        std::string bid = get_or_create_binding_id(name);
        auto it = var_values.find(name);
        std::string old_val_json = (it != var_values.end()) ? it->second : "{\"kind\":\"uninitialized\"}";
        var_values[name] = new_val_json;

        std::string payload = "{\"binding_id\":\"" + bid + "\","
                            + "\"name\":\"" + escape_json(name) + "\","
                            + "\"old_value\":" + old_val_json + ","
                            + "\"new_value\":" + new_val_json + "}";
        emit_raw_event("VAR_WRITE", line, payload);
    }

    template <typename T>
    void on_array_write(const char* name, int index, const T& val, int line) {
        std::string val_json = value_to_json(val);
        std::string payload = "{\"container_id\":\"" + escape_json(name) + "\","
                            + "\"kind\":\"ARRAY\","
                            + "\"op\":\"SET_INDEX\","
                            + "\"indices\":[" + std::to_string(index) + "],"
                            + "\"values\":[" + val_json + "]}";
        emit_raw_event("CONTAINER_OP", line, payload);
    }
};

// --- Dynamic Memory & Object Mutation Function Wrappers ---

template <typename T>
inline T* al_new(T* ptr, const char* type_name, int line) {
    if (ptr) {
        uintptr_t addr = reinterpret_cast<uintptr_t>(ptr);
        std::string obj_id = ObjectRegistry::instance().register_allocation(
            addr,
            type_name,
            sizeof(T),
            line
        );
        std::ostringstream ss;
        ss << "0x" << std::hex << addr;
        std::string payload = "{\"object_id\":\"" + obj_id + "\","
                            + "\"type_name\":\"" + escape_json(type_name) + "\","
                            + "\"fields\":{},"
                            + "\"debug_meta\":{\"native_address\":\"" + ss.str() + "\",\"size\":" + std::to_string(sizeof(T)) + "}}";
        Runtime::instance().emit_raw_event("OBJECT_ALLOCATE", line, payload);
    }
    return ptr;
}

template <typename T>
inline T* al_delete(T* ptr, int line) {
    if (ptr) {
        std::string obj_id, type_name, old_fields_json;
        uintptr_t addr = reinterpret_cast<uintptr_t>(ptr);
        if (ObjectRegistry::instance().deallocate(addr, obj_id, type_name, old_fields_json)) {
            std::ostringstream ss;
            ss << "0x" << std::hex << addr;
            std::string payload = "{\"object_id\":\"" + obj_id + "\","
                                + "\"type_name\":\"" + escape_json(type_name) + "\","
                                + "\"old_fields\":" + old_fields_json + ","
                                + "\"debug_meta\":{\"native_address\":\"" + ss.str() + "\"}}";
            Runtime::instance().emit_raw_event("OBJECT_DEALLOCATE", line, payload);
        }
    }
    return ptr;
}

template <typename T>
inline void al_stack_alloc(T* ptr, const char* type_name, int line) {
    if (ptr) {
        uintptr_t addr = reinterpret_cast<uintptr_t>(ptr);
        if (ObjectRegistry::instance().active_addr_to_id.find(addr) == ObjectRegistry::instance().active_addr_to_id.end()) {
            std::string obj_id = ObjectRegistry::instance().register_allocation(
                addr,
                type_name,
                sizeof(T),
                line
            );
            std::ostringstream ss;
            ss << "0x" << std::hex << addr;
            std::string payload = "{\"object_id\":\"" + obj_id + "\","
                                + "\"type_name\":\"" + escape_json(type_name) + "\","
                                + "\"fields\":{},"
                                + "\"debug_meta\":{\"native_address\":\"" + ss.str() + "\",\"size\":" + std::to_string(sizeof(T)) + ",\"is_stack\":true}}";
            Runtime::instance().emit_raw_event("OBJECT_ALLOCATE", line, payload);
        }
    }
}

template <typename ObjT, typename ValT>
inline void al_field_write(ObjT* obj_ptr, const char* field_name, const ValT& new_val, int line) {
    if (!obj_ptr) return;
    uintptr_t addr = reinterpret_cast<uintptr_t>(obj_ptr);
    if (ObjectRegistry::instance().active_addr_to_id.find(addr) == ObjectRegistry::instance().active_addr_to_id.end()) {
        al_stack_alloc(obj_ptr, "Object", line);
    }
    std::string obj_id = ObjectRegistry::instance().get_or_register_address(addr);
    
    auto& reg = ObjectRegistry::instance().registry[obj_id];
    auto it = reg.fields.find(field_name);
    std::string old_val_json = (it != reg.fields.end()) ? it->second : "{\"kind\":\"uninitialized\"}";
    std::string new_val_json = value_to_json(new_val);
    reg.fields[field_name] = new_val_json;

    std::string payload = "{\"object_id\":\"" + obj_id + "\","
                        + "\"field\":\"" + escape_json(field_name) + "\","
                        + "\"old_value\":" + old_val_json + ","
                        + "\"new_value\":" + new_val_json + "}";
    Runtime::instance().emit_raw_event("OBJECT_MUTATE", line, payload);
}

template <typename PtrT, typename ValT>
inline void al_deref_write(PtrT* ptr, const ValT& new_val, int line) {
    if (!ptr) return;
    uintptr_t addr = reinterpret_cast<uintptr_t>(ptr);
    if (ObjectRegistry::instance().active_addr_to_id.find(addr) == ObjectRegistry::instance().active_addr_to_id.end()) {
        al_stack_alloc(ptr, "Object", line);
    }
    std::string obj_id = ObjectRegistry::instance().get_or_register_address(addr);
    
    auto& reg = ObjectRegistry::instance().registry[obj_id];
    auto it = reg.fields.find("value");
    std::string old_val_json = (it != reg.fields.end()) ? it->second : "{\"kind\":\"uninitialized\"}";
    std::string new_val_json = value_to_json(new_val);
    reg.fields["value"] = new_val_json;

    std::string payload = "{\"object_id\":\"" + obj_id + "\","
                        + "\"field\":\"value\","
                        + "\"old_value\":" + old_val_json + ","
                        + "\"new_value\":" + new_val_json + "}";
    Runtime::instance().emit_raw_event("OBJECT_MUTATE", line, payload);

    auto it_var = Runtime::instance().active_var_addrs.find(addr);
    if (it_var != Runtime::instance().active_var_addrs.end()) {
        Runtime::instance().on_var_write(it_var->second.name.c_str(), new_val, line);
    }
}

// --- Container & String Semantic Operation Wrappers ---

template <typename T>
inline void al_container_push(const char* name, const char* kind, const T& val, int line) {
    std::string val_json = value_to_json(val);
    std::string payload = "{\"container_id\":\"" + escape_json(name) + "\","
                        + "\"kind\":\"" + escape_json(kind) + "\","
                        + "\"op\":\"PUSH\","
                        + "\"values\":[" + val_json + "]}";
    Runtime::instance().emit_raw_event("CONTAINER_OP", line, payload);
}

template <typename T>
inline void al_container_pop(const char* name, const char* kind, const T& popped_val, int line) {
    std::string val_json = value_to_json(popped_val);
    std::string payload = "{\"container_id\":\"" + escape_json(name) + "\","
                        + "\"kind\":\"" + escape_json(kind) + "\","
                        + "\"op\":\"POP\","
                        + "\"old_values\":[" + val_json + "]}";
    Runtime::instance().emit_raw_event("CONTAINER_OP", line, payload);
}

template <typename ContT>
inline void al_container_clear(const char* name, const char* kind, const ContT& cont, int line) {
    std::ostringstream ss_vals;
    ss_vals << "[";
    bool first = true;
    for (const auto& elem : cont) {
        if (!first) ss_vals << ",";
        ss_vals << value_to_json(elem);
        first = false;
    }
    ss_vals << "]";
    std::string payload = "{\"container_id\":\"" + escape_json(name) + "\","
                        + "\"kind\":\"" + escape_json(kind) + "\","
                        + "\"op\":\"CLEAR\","
                        + "\"old_values\":" + ss_vals.str() + "}";
    Runtime::instance().emit_raw_event("CONTAINER_OP", line, payload);
}

template <typename K, typename V>
inline void al_map_insert(const char* name, const K& key, const V& val, int line) {
    std::ostringstream ss_k;
    ss_k << key;
    std::string val_json = value_to_json(val);
    std::string payload = "{\"container_id\":\"" + escape_json(name) + "\","
                        + "\"kind\":\"MAP\","
                        + "\"op\":\"INSERT\","
                        + "\"meta\":{\"" + escape_json(ss_k.str()) + "\":" + val_json + "}}";
    Runtime::instance().emit_raw_event("CONTAINER_OP", line, payload);
}

template <typename K, typename MapT>
inline void al_map_erase(const char* name, const K& key, const MapT& map, int line) {
    std::ostringstream ss_k;
    ss_k << key;
    std::string old_val_json = "{\"kind\":\"uninitialized\"}";
    auto it = map.find(key);
    if (it != map.end()) {
        old_val_json = value_to_json(it->second);
    }
    std::string payload = "{\"container_id\":\"" + escape_json(name) + "\","
                        + "\"kind\":\"MAP\","
                        + "\"op\":\"ERASE\","
                        + "\"meta\":{\"" + escape_json(ss_k.str()) + "\":" + old_val_json + "},"
                        + "\"old_meta\":{\"" + escape_json(ss_k.str()) + "\":" + old_val_json + "}}";
    Runtime::instance().emit_raw_event("CONTAINER_OP", line, payload);
}

template <typename MapT>
inline void al_map_clear(const char* name, const MapT& map, int line) {
    std::ostringstream ss_meta;
    ss_meta << "{";
    bool first = true;
    for (const auto& pair : map) {
        if (!first) ss_meta << ",";
        std::ostringstream ss_k;
        ss_k << pair.first;
        ss_meta << "\"" << escape_json(ss_k.str()) << "\":" << value_to_json(pair.second);
        first = false;
    }
    ss_meta << "}";
    std::string payload = "{\"container_id\":\"" + escape_json(name) + "\","
                        + "\"kind\":\"MAP\","
                        + "\"op\":\"CLEAR\","
                        + "\"old_meta\":" + ss_meta.str() + "}";
    Runtime::instance().emit_raw_event("CONTAINER_OP", line, payload);
}

inline void al_string_write(const char* name, const std::string& s, int line) {
    Runtime::instance().on_var_write(name, s, line);
}

} // namespace algolens

// Global Macros for Concise Instrumentation
#define AL_PROG_START(entry_name, line) ::algolens::Runtime::instance().on_prog_start(entry_name, line)
#define AL_STEP_LINE(line) ::algolens::Runtime::instance().on_step_line(line)
#define AL_FRAME_PUSH(func_name, line) ::algolens::Runtime::instance().on_frame_push(func_name, line)
#define AL_FRAME_POP(line, ret_val) ::algolens::Runtime::instance().on_frame_pop(line, ret_val)
#define AL_FRAME_POP_VOID(line) ::algolens::Runtime::instance().on_frame_pop_void(line)
#define AL_SCOPE_ENTER(kind, line) ::algolens::Runtime::instance().on_scope_enter(kind, line)
#define AL_SCOPE_EXIT(line) ::algolens::Runtime::instance().on_scope_exit(line)
#define AL_VAR_DECLARE(name, type_str, val, line) ::algolens::Runtime::instance().on_var_declare(name, type_str, val, line)
#define AL_VAR_WRITE(name, val, line) ::algolens::Runtime::instance().on_var_write(name, val, line)
#define AL_ARRAY_WRITE(name, index, val, line) ::algolens::Runtime::instance().on_array_write(name, index, val, line)
#define AL_FIELD_WRITE(obj_ptr, field_name, val, line) ::algolens::al_field_write(obj_ptr, field_name, val, line)
#define AL_DEREF_WRITE(ptr, val, line) ::algolens::al_deref_write(ptr, val, line)
#define AL_STACK_ALLOC(ptr, type_name, line) ::algolens::al_stack_alloc(ptr, type_name, line)
#define AL_CONTAINER_PUSH(name, kind, val, line) ::algolens::al_container_push(name, kind, val, line)
#define AL_CONTAINER_POP(name, kind, val, line) ::algolens::al_container_pop(name, kind, val, line)
#define AL_CONTAINER_CLEAR(name, kind, cont, line) ::algolens::al_container_clear(name, kind, cont, line)
#define AL_MAP_INSERT(name, key, val, line) ::algolens::al_map_insert(name, key, val, line)
#define AL_MAP_ERASE(name, key, map, line) ::algolens::al_map_erase(name, key, map, line)
#define AL_MAP_CLEAR(name, map, line) ::algolens::al_map_clear(name, map, line)
#define AL_STRING_WRITE(name, s, line) ::algolens::al_string_write(name, s, line)
