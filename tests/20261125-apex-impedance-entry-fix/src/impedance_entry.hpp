#pragma once
#include <array>
#include <cmath>
#include <cstdint>
#include <functional>

namespace impedance_entry {
struct Feedback {
    std::uint32_t frame{};
    std::array<int, 2> state{}, error{};
    std::array<std::array<double, 7>, 2> position{}, velocity{};
};
using Limits = std::array<std::array<std::array<double, 2>, 7>, 2>;
struct Operations {
    std::function<Feedback()> read;
    std::function<void()> wait;
    std::function<bool(const Feedback&)> seed;
    std::function<bool(int)> position, pd;
    std::function<void(const char*, const Feedback&)> failure;
};
inline bool valid(const Feedback& f, const Limits& limits) {
    for (int side=0; side<2; ++side) {
        if (f.error[side] || (f.state[side]!=0 && f.state[side]!=1 && f.state[side]!=2)) return false;
        for (int j=0; j<7; ++j) {
            const double q=f.position[side][j], v=f.velocity[side][j];
            if (!std::isfinite(q) || !std::isfinite(v) || std::abs(v)>1.0 ||
                !std::isfinite(limits[side][j][0]) || !std::isfinite(limits[side][j][1]) ||
                q<=limits[side][j][0]+1.0 || q>=limits[side][j][1]-1.0) return false;
        }
    }
    return true;
}
inline bool enter(Operations& op, const Limits& limits) {
    Feedback first=op.read(), current=first;
    auto fail=[&](const char* stage) { op.failure(stage, current); return false; };
    bool fresh=false;
    for (int i=0; i<50; ++i) {
        op.wait(); current=op.read();
        if (current.frame!=first.frame) { fresh=true; break; }
    }
    if (!fresh || !valid(current, limits)) return fail("fresh stationary feedback/limits");
    if (current.state[0]==2 && current.state[1]==2) return true;
    const Feedback hold=current;
    if (!op.seed(hold)) return fail("seed current position");
    for (int side=0; side<2; ++side) {
        if (hold.state[side]==0 && !op.position(side)) {
            current=op.read(); return fail("position preparation");
        }
    }
    int stable=0;
    std::uint32_t previous=current.frame;
    for (int i=0; i<300 && stable<20; ++i) {
        op.wait(); current=op.read();
        if (!valid(current, limits)) return fail("position feedback/limits");
        bool expected=true;
        for (int side=0; side<2; ++side) {
            if (current.state[side]!=(hold.state[side]==2 ? 2 : 1)) expected=false;
            for (int j=0; j<7; ++j)
                if (std::abs(current.position[side][j]-hold.position[side][j])>2.0)
                    return fail("unexpected displacement");
        }
        stable=expected && current.frame!=previous ? stable+1 : 0;
        previous=current.frame;
    }
    if (stable<20) return fail("position settle timeout");
    for (int side=0; side<2; ++side) {
        if (hold.state[side]!=2 && !op.pd(side)) {
            current=op.read(); return fail("PD entry");
        }
    }
    for (int i=0; i<100; ++i) {
        op.wait(); current=op.read();
        if (!valid(current, limits)) return fail("PD feedback");
        if (current.state[0]==2 && current.state[1]==2 && current.frame!=previous) return true;
    }
    return fail("PD feedback timeout");
}
} // namespace impedance_entry
