#include <thing/thing.pbng.h>

int main() {
  thing::AddressBook ab;
  {
    thing::Person p;
    p.set_email("bob@foobar");
    ab.person_vec().push_back(std::move(p));
  }
  return 0;
}
