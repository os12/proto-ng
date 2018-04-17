#include <cassert>
#include <iostream>
#include <unordered_set>
#include <set>

#include <thing/containers.pbng.h>
#include <thing/ext.pbng.h>
#include <thing/thing.pbng.h>
#include <thing/foreign.pbng.h>

namespace {

void BasicAPI() {
  // Next-gen protobuf API
  thing::AddressBook ab;
  {
    thing::Person p;
    p.set_email("bob@foobar");
    p.add_phone_vec()->set_number("111");
    p.add_phone_vec()->set_number("222");
    p.phone_vec().at(0).set_itype(thing::Person::PhoneNumber::HOME);
    ab.person_vec().push_back(std::move(p));
  }

  // Debug output
  std::cout << "AB:\n" << ab.DebugString();

  // Deprecated protobuf API
  //assert(ab.person_vec().size() == ab.person_vec_size());
}

void Equality() {
  // Basic equality and total ordering.
  thing::Person p1, p2;
  assert(p1 == p2);
  assert(!(p1 != p2));
  assert(p1 == thing::Person::default_instance());
  p1.set_id(5);
  assert(p1 > p2);
  assert(p1 != p2);

  // A proto3-style feature - it's a scalar with the default value
  p1.set_id(0);
  assert(p1 == p2);
  p1.clear_id();
  assert(p1 == p2);

  // A proto3-style feature - "0" is default
  p1.set_ph_type_v3(thing::Person::PhoneNumber::WORK);
  assert(p1 > p2);
  p1.set_ph_type_v3(thing::Person::PhoneNumber::MOBILE);
  assert(p1 == p2);
  assert(p1 == thing::Person::default_instance());

  // a proto3-style feature - sub-messages with default content are as good
  // as missing
  thing::WithForwardRef m1, m2;
  assert(m1 == m2);
  m1.member().set_field(0);
  assert(m1 == m2);
}

void SetsHashes() {
  {
    thing::Person p;
    p.set_id(5);
    std::set<thing::Person> set = {p};
    assert(set.size() == 1);
  }

  // Hashing
  std::unordered_set<thing::Block> set;
  {
    thing::Block b1;
    b1.set_id(1);
    set.insert(b1);
    assert(set.count(b1) == 1);

    thing::Block b2;
    b2.set_id(2);
    set.insert(b2);
    assert(set.count(b2) == 1);
    auto rv = set.insert(b2);
    assert(!rv.second);
    assert(*rv.first == b2);
    assert(*rv.first != b1);

    // equivalence
    auto b3 = b2;
    assert(b2 == b3);
    assert(std::equal_to<thing::Block>()(b2, b3));
    b3.set_email("foobar@domain");
    assert(std::equal_to<thing::Block>()(b2, b3));
    assert(b2 != b3);
    rv = set.insert(b3);
    assert(!rv.second);
    assert(std::equal_to<thing::Block>()(*rv.first, b3));
    assert(*rv.first == b2);
  }
}

void Extensions() {
  thing::Person p;
  p.HasExtension(thing::ext100);
  thing::GlobalExtension *gext = p.MutableExtension(thing::ext100);

  p.HasExtension(thing::NestedExtension::ext200);
  thing::NestedExtension *next =
      p.MutableExtension(thing::NestedExtension::ext200);
}

} // namespace

int main() {
  BasicAPI();
  Extensions();
  Equality();
  SetsHashes();

  std::cout << "All good!\n";
  return 0;
}
