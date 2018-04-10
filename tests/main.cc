#include <cassert>
#include <iostream>
#include <set>

#include <thing/ext.pbng.h>
#include <thing/thing.pbng.h>

int main() {
  // Next-gen protobuf API
  thing::AddressBook ab;
  {
    thing::Person p;
    p.set_email("bob@foobar");
    ab.person_vec().push_back(std::move(p));
  }

  // Deprecated protobuf API
  //assert(ab.person_vec().size() == ab.person_vec_size());

  // Deprecated protobuf v2 extensions
  {
    thing::Person p;
    p.HasExtension(thing::ext100);
    thing::GlobalExtension *gext =
        p.MutableExtension(thing::ext100);

    p.HasExtension(thing::NestedExtension::ext200);
    thing::NestedExtension *next =
        p.MutableExtension(thing::NestedExtension::ext200);
  }

  {
    thing::Person p;
    p.set_id(5);
    std::set<thing::Person> set = {p};
    assert(set.size() == 1);
  }

  thing::Person p1, p2;
  assert(p1 == p2);
  assert(!(p1 != p2));
  assert(p1 == thing::Person::default_instance());
  p1.set_id(5);
  assert(p1 > p2);
  assert(p1 != p2);

  p1.set_id(0);
  assert(p1 == p2);     // a proto3-style check - it's a scalar with the default value
  p1.clear_id();
  assert(p1 == p2);

  p1.set_ph_type_v3(thing::Person::PhoneNumber::WORK);
  assert(p1 > p2);
  p1.set_ph_type_v3(thing::Person::PhoneNumber::MOBILE); // a proto3-style check - "0" is default
  assert(p1 == p2);

  assert(p1 == thing::Person::default_instance());

  std::cout << "All good!\n";
  return 0;
}
