#include "src/impedance_entry.hpp"
#include <cassert>
#include <limits>
#include <string>
#include <vector>
using namespace impedance_entry;
struct Fake {
    Feedback f;
    Limits limits{};
    bool frozen=false, position_failure=false, pd_failure=false, drift=false;
    std::string failed;
    std::vector<std::string> calls;
    Fake() { for (auto& arm:limits) for (auto& q:arm) q={-90,90}; }
    Operations operations() {
        return {
            [&]{return f;}, [&]{if(!frozen)++f.frame;},
            [&](const Feedback&){calls.push_back("seed");return true;},
            [&](int s){calls.push_back("P"+std::to_string(s));if(position_failure){f.state[s]=100;f.error[s]=102;return false;}f.state[s]=1;if(drift)f.position[s][0]=3;return true;},
            [&](int s){calls.push_back("D"+std::to_string(s));if(pd_failure&&s==1){f.state[s]=100;f.error[s]=106;return false;}f.state[s]=2;return true;},
            [&](const char* why,const Feedback&){failed=why;}
        };
    }
    bool run(){auto o=operations();return enter(o,limits);}
};
int main(){
    {Fake x;assert(x.run());assert((x.calls==std::vector<std::string>{"seed","P0","P1","D0","D1"}));}
    {Fake x;x.f.state={2,2};assert(x.run());assert(x.calls.empty());}
    {Fake x;x.f.state={2,0};assert(x.run());assert((x.calls==std::vector<std::string>{"seed","P1","D1"}));}
    {Fake x;x.f.state={1,1};assert(x.run());assert((x.calls==std::vector<std::string>{"seed","D0","D1"}));}
    {Fake x;x.f.state[1]=100;x.f.error[1]=106;assert(!x.run());assert(x.calls.empty());}
    {Fake x;x.frozen=true;assert(!x.run());assert(x.calls.empty());}
    {Fake x;x.f.velocity[1][5]=2;assert(!x.run());assert(x.calls.empty());}
    {Fake x;x.f.position[1][5]=89.5;assert(!x.run());assert(x.calls.empty());}
    {Fake x;x.f.position[1][5]=std::numeric_limits<double>::quiet_NaN();assert(!x.run());assert(x.calls.empty());}
    {Fake x;x.position_failure=true;assert(!x.run());assert(x.calls.back()=="P0");}
    {Fake x;x.drift=true;assert(!x.run());assert(x.failed=="unexpected displacement");assert(x.calls.back()=="P1");}
    {Fake x;x.pd_failure=true;assert(!x.run());assert(x.f.state[0]==2);assert(x.f.error[1]==106);assert(x.calls.back()=="D1");}
}
