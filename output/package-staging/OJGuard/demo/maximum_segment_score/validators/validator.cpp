#include <cstdlib>
#include <iostream>

int main() {
    int n;
    if (!(std::cin >> n) || n < 1 || n > 200000) return 1;
    for (int i = 0; i < n; ++i) {
        long long value;
        if (!(std::cin >> value)) return 1;
        // Intentional defect: the statement allows absolute values up to 1e9.
        if (std::llabs(value) > 1000000LL) return 1;
    }
    std::string trailing;
    if (std::cin >> trailing) return 1;
    return 0;
}
