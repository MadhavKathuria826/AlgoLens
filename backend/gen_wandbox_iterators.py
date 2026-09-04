import urllib.request
import json

def run_wandbox(code, func_name):
    wrapper = f"""#include <iostream>
#include <vector>
#include <map>
#include <set>
#include <string>
#include <utility>

{code}

int main() {{
    auto res = {func_name}();
    std::cout << "RETURN:" << res << std::endl;
    return 0;
}}
"""
    payload = {'compiler': 'gcc-13.2.0', 'code': wrapper, 'save': True}
    req = urllib.request.Request(
        'https://wandbox.org/api/compile.json',
        data=json.dumps(payload).encode('utf-8'),
        headers={'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'}
    )
    resp = urllib.request.urlopen(req, timeout=20)
    res = json.loads(resp.read().decode('utf-8'))
    permlink = res.get("permlink")
    url = res.get("url")
    output = res.get("program_output", "").strip()

    # Fetch back to verify permlink exists on Wandbox
    verify_url = f"https://wandbox.org/api/permlink/{permlink}"
    v_req = urllib.request.Request(verify_url, headers={'User-Agent': 'Mozilla/5.0'})
    v_resp = urllib.request.urlopen(v_req, timeout=10)
    v_data = json.loads(v_resp.read().decode('utf-8'))
    v_output = v_data['result']['program_output'].strip()

    print(f"=== {func_name} ===")
    print("Status:", res.get("status"))
    print("Output:", output)
    print("Permlink:", permlink)
    print("URL:", url)
    print("Verified Fetch Output:", v_output)
    print()

if __name__ == "__main__":
    run_wandbox("""
int test_map_find() {
    std::map<std::string, int> m;
    m.insert(std::make_pair("apple", 10));
    m.insert(std::make_pair("banana", 20));
    bool found = (m.find("apple") != m.end());
    bool not_found = (m.find("cherry") == m.end());
    if (found && not_found) return 1;
    return 0;
}
""", "test_map_find")

    run_wandbox("""
int test_set_find() {
    std::set<int> s;
    s.insert(100);
    s.insert(200);
    bool found = (s.find(100) != s.end());
    bool not_found = (s.find(999) == s.end());
    if (found && not_found) return 1;
    return 0;
}
""", "test_set_find")

    run_wandbox("""
int test_vector_iter() {
    std::vector<int> v;
    v.push_back(10);
    v.push_back(20);
    v.push_back(30);
    int first_elem = 0;
    if (v.begin() != v.end()) {
        first_elem = *v.begin();
    }
    return first_elem;
}
""", "test_vector_iter")

    run_wandbox("""
int test_reg() {
    std::map<std::string, int> m;
    m.insert(std::make_pair("x", 1));
    bool f = (m.find("y") != m.end());
    if (f) return 1;
    return 0;
}
""", "test_reg")
