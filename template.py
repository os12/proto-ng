class Templates:
    infra = '''#pragma once
#include <functional>

namespace proto_ng {

// Support for extensions
namespace detail {
template<typename Extension>
struct Helper {};
template<typename Extension>
inline int ResolveField(Extension) { return -1; }
}  // detail

// Support for hashing, comes from Boost.
template <typename T>
inline void hash_combine(std::size_t& seed, const T& v) {
    seed ^= std::hash<T>()(v) + 0x9e3779b9 + (seed << 6) + (seed >> 2);
}

}  // proto_ng
'''

    impl = r'''#include <bitset>
#include <sstream>

namespace {

std::string Escape(const std::string& data) {
    char buf[16];

    std::string rv = "\"";
    rv.resize(data.size() + data.size() / 10);
    for (char c : data) {
        if (!isprint(c)) {
            sprintf(buf, "\\x%02x", c);
            rv += buf;
            continue;
        }

        switch (c) {
        case '\\':
        case '"':
            rv += '\\';
        default:
            rv += c;
        }
    }
    rv += "\"";
    return rv;
}

}

'''
