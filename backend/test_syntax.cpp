#include <iostream>
#include <vector>
#include <queue>
#include <utility>
#include <functional>

int test_pair() {
    std::pair<int, int> p = std::make_pair(10, 20);
    p.first = p.first + 5;
    p.second = p.second * 2;
    return p.first + p.second;
}

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

int test_pq_pair() {
    std::priority_queue<std::pair<int, int>, std::vector<std::pair<int, int>>, std::greater<std::pair<int, int>>> pq;
    pq.push(std::make_pair(5, 101));
    pq.push(std::make_pair(1, 102));
    pq.push(std::make_pair(3, 103));
    std::pair<int, int> top_p = pq.top();
    return top_p.first * 1000 + top_p.second;
}

int main() {
    return 0;
}
