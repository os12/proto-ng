#include <cassert>

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

  return 0;
}
