#pragma once
/**
 * AlgoLens Native C++ Runtime Instrumentation Header
 * 
 * Embeds observation hooks into natively compiled C++ programs.
 * Emits AlgoLens Event Protocol v2.1 JSON Lines stream.
 * Isolates event output with the [ALGOLENS_EVENT] transport prefix.
 */

#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <unordered_map>
#include <chrono>
#include <iomanip>
#include <cstdint>
#include <type_traits>

namespace algolens {

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
    std::ostringstream ss;
    ss << "0x" << std::hex << reinterpret_cast<uintptr_t>(ptr);
    return "{\"kind\":\"object_ref\",\"object_id\":\"" + ss.str() + "\"}";
}

// Fallback for unspecialized types
template <typename T>
typename std::enable_if<!std::is_pointer<T>::value && !std::is_arithmetic<T>::value, std::string>::type
value_to_json(const T&) {
    return "{\"kind\":\"primitive\",\"type_name\":\"unknown\",\"value\":\"<unsupported_value>\"}";
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

    // --- Hooks ---

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
        if (frame_stack.size() > 1) frame_stack.pop_back();
        if (scope_stack.size() > 1) scope_stack.pop_back();
    }

    void on_frame_pop_void(int line) {
        std::string payload = "{\"return_value\":null}";
        emit_raw_event("FRAME_POP", line, payload);
        if (frame_stack.size() > 1) frame_stack.pop_back();
        if (scope_stack.size() > 1) scope_stack.pop_back();
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
        std::string bid = get_or_create_binding_id(name);
        std::string new_val_json = value_to_json(new_val);
        
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
