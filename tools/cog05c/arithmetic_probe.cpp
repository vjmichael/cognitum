#include <boost/multiprecision/cpp_int.hpp>
#include <boost/rational.hpp>
#include <gmpxx.h>
#include <iostream>
#include <sstream>
#include <stdexcept>
using I=boost::multiprecision::cpp_int;
using R=boost::rational<I>;
int main(){
    I n=(I(1)<<8191)+1, d=(I(1)<<4095)+3;
    mpz_class gn(n.str()),gd(d.str());
    R x(n,d), y(-7,19), z=(x+y)*(x-y)/x;
    mpq_class gx(gn,gd),gy(-7,19);gx.canonicalize();
    mpq_class gz=(gx+gy)*(gx-gy)/gx;gz.canonicalize();
    std::ostringstream s;s<<z.numerator()<<'/'<<z.denominator();
    if(s.str()!=gz.get_str())return 1;
    try{R negative(3,-6);if(negative!=R(-1,2))return 2;}catch(const boost::bad_rational&){std::cerr<<"raw negative denominator refused by Boost; normalize explicitly\n";}
    auto canonical=[](I n,I d){if(d==0)throw std::invalid_argument("zero denominator");if(d<0){n=-n;d=-d;}return R(n,d);};
    if(canonical(0,-3)!=R(0) || canonical(3,-6)!=R(-1,2))return 3;
    try{canonical(1,0);return 4;}catch(const std::invalid_argument&){};
    std::cout<<s.str()<<'\n';
}
