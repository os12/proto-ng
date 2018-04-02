PROTOC := ../protoc-ng.py

all: build/test

build/test: build/magneto/magneto.pbng.o build/google/protobuf/timestamp.pbng.o build/main.o
	g++ -o build/test $?

build/main.o: main.cc
	g++ -c -I build -o $@ $<

build/magneto/magneto.pbng.cc: magneto/magneto.proto google/protobuf/timestamp.proto
	$(PROTOC) -I . --cpp_out build $<
build/google/protobuf/timestamp.pbng.cc: google/protobuf/timestamp.proto
	$(PROTOC) -I . --cpp_out build $<

build/magneto/magneto.pbng.o: build/magneto/magneto.pbng.cc
	g++ -c -I build -o $@ $<
build/google/protobuf/timestamp.pbng.o: build/google/protobuf/timestamp.pbng.cc
	g++ -c -I build -o $@ $<
