from main import execute_code
from models import CodeExecutionRequest
import json

req_map = CodeExecutionRequest(
    language='cpp',
    code='''#include <map>
int map_has_key(int target) {
    std::map<int, int> m;
    m.insert(std::make_pair(100, 1));
    m.insert(std::make_pair(200, 2));
    if (m.find(target) != m.end()) {
        return 1;
    }
    return 0;
}''',
    test_case="target = 100"
)
res_map = execute_code(req_map)
print("=== RAW MAP FIND RESPONSE JSON ===")
print(res_map.model_dump_json(indent=2))

req_vec = CodeExecutionRequest(
    language='cpp',
    code='''#include <vector>
int vector_first(std::vector<int> nums) {
    if (nums.begin() != nums.end()) {
        return *nums.begin();
    }
    return -1;
}''',
    test_case="nums = [42, 99, 100]"
)
res_vec = execute_code(req_vec)
print("=== RAW VECTOR BEGIN RESPONSE JSON ===")
print(res_vec.model_dump_json(indent=2))
