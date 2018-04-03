#include <magneto/magneto.pbng.h>

int main() {
  tutorial::AddressBook ab;
  {
    tutorial::Person p;
    p.set_email("bob@foobar");
    ab.person_vec().push_back(std::move(p));
  }
  return 0;
}
