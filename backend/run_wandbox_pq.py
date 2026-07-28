import urllib.request
import json

def run_wandbox(code, func_name):
    wrapper = f"""#include <iostream>
#include <vector>
#include <string>
#include <queue>
#include <utility>
#include <functional>

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
    print(f"=== {func_name} ===")
    print("Status:", res.get("status"))
    print("Output:", res.get("program_output", "").strip())
    print("Permlink:", res.get("permlink"))
    print("URL:", res.get("url"))
    print()

if __name__ == "__main__":
    run_wandbox("""
int test_pq_max() {
    std::priority_queue<int> pq;
    pq.push(10);
    pq.push(30);
    pq.push(20);
    int top1 = pq.top();
    pq.pop();
    int top2 = pq.top();
    return top1 * 100 + top2;
}
""", "test_pq_max")

    run_wandbox("""
int test_pq_min() {
    std::priority_queue<int, std::vector<int>, std::greater<int>> pq;
    pq.push(30);
    pq.push(10);
    pq.push(20);
    int top1 = pq.top();
    pq.pop();
    int top2 = pq.top();
    return top1 * 100 + top2;
}
""", "test_pq_min")

    run_wandbox("""
int test_pq_pair() {
    std::priority_queue<std::pair<int, int>, std::vector<std::pair<int, int>>, std::greater<std::pair<int, int>>> pq;
    pq.push(std::make_pair(5, 101));
    pq.push(std::make_pair(1, 102));
    pq.push(std::make_pair(3, 103));
    std::pair<int, int> top_p = pq.top();
    return top_p.first * 1000 + top_p.second;
}
""", "test_pq_pair")
