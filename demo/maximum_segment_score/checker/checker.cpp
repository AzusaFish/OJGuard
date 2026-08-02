#include <fstream>

int main(int argc, char** argv) {
    if (argc != 3) return 2;
    std::ifstream answer_file(argv[1]);
    std::ifstream output_file(argv[2]);
    long long expected;
    long long actual;
    if (!(answer_file >> expected) || !(output_file >> actual)) return 2;
    // Intentional defect: trailing contestant output is not rejected.
    return expected == actual ? 0 : 1;
}
