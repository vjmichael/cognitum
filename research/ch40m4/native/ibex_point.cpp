#include <ibex.h>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <string>

int main(int argc, char** argv) {
    if (argc != 5) {
        std::cerr << "usage: ibex_point model.bch b0 b1 b2\n";
        return 2;
    }
    try {
        ibex::System system(argv[1], 0);
        if (system.nb_var != 3 || !system.goal) {
            std::cerr << "unexpected model shape\n";
            return 3;
        }
        ibex::IntervalVector point(3);
        for (int i = 0; i < 3; ++i) {
            const double x = std::stod(argv[i + 2]);
            if (!std::isfinite(x)) return 4;
            point[i] = ibex::Interval(x, x);
        }
        const ibex::Interval objective = system.goal->eval(point);
        if (objective.is_empty() || !std::isfinite(objective.lb()) ||
            !std::isfinite(objective.ub())) {
            std::cerr << "nonfinite objective interval\n";
            return 5;
        }
        std::cout << std::setprecision(17) << objective.lb() << " " << objective.ub() << "\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "native exception: " << e.what() << "\n";
        return 6;
    }
}
