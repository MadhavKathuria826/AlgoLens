#include <iostream>
#include <vector>
#include <map>
#include <set>
#include <string>
#include <utility>

int test_map_find() {
    std::map<std::string, int> m;
    m.insert(std::make_pair("apple", 10));
    m.insert(std::make_pair("banana", 20));
    bool found = (m.find("apple") != m.end());
    bool not_found = (m.find("cherry") == m.end());
    if (found && not_found) return 1;
    return 0;
}

int test_set_find() {
    std::set<int> s;
    s.insert(100);
    s.insert(200);
    bool found = (s.find(100) != s.end());
    bool not_found = (s.find(999) == s.end());
    if (found && not_found) return 1;
    return 0;
}

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

int test_reg() {
    std::map<std::string, int> m;
    m.insert(std::make_pair("x", 1));
    bool f = (m.find("y") != m.end());
    if (f) return 1;
    return 0;
}

int main() {
    return 0;
}
