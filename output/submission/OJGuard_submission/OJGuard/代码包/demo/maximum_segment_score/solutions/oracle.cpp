#include <algorithm>
#include <iostream>
#include <limits>

int main() {
    int n;
    std::cin >> n;
    long long best = std::numeric_limits<long long>::lowest();
    long long current = 0;
    for (int i = 0; i < n; ++i) {
        long long value;
        std::cin >> value;
        current = std::max(value, current + value);
        best = std::max(best, current);
    }
    std::cout << best << '\n';
}
