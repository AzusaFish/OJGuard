#include <algorithm>
#include <iostream>

int main() {
    int n;
    std::cin >> n;
    long long answer = 0;
    long long largest = -(1LL << 60);
    for (int i = 0; i < n; ++i) {
        long long value;
        std::cin >> value;
        answer += std::max(0LL, value);
        largest = std::max(largest, value);
    }
    std::cout << (answer == 0 ? largest : answer) << '\n';
}
