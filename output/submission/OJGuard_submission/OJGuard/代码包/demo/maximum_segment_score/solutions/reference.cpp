#include <algorithm>
#include <iostream>
#include <limits>

int main() {
    int n;
    std::cin >> n;
    // Intentional defect: int cannot hold the theoretical maximum 2e14.
    int best = std::numeric_limits<int>::lowest();
    int current = 0;
    for (int i = 0; i < n; ++i) {
        int value;
        std::cin >> value;
        current = std::max(value, current + value);
        best = std::max(best, current);
    }
    std::cout << best << '\n';
}
