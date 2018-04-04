PROTOC := ../protoc-ng.py
CXX_OPTIONS := -std=c++14 -I build -g

all: build/test

build/test: build/magneto/magneto.pbng.o build/google/protobuf/timestamp.pbng.o build/main.o
	g++ -o build/test $^

build/main.o: main.cc
	g++ -c $(CXX_OPTIONS) -o $@ $<

build/magneto/magneto.pbng.cc: magneto/magneto.proto google/protobuf/timestamp.proto
	$(PROTOC) -I . --cpp_out build $<
build/google/protobuf/timestamp.pbng.cc: google/protobuf/timestamp.proto
	$(PROTOC) -I . --cpp_out build $<

build/magneto/magneto.pbng.o: build/magneto/magneto.pbng.cc build/google/protobuf/timestamp.pbng.cc
	g++ -c $(CXX_OPTIONS) -o $@ $<
build/google/protobuf/timestamp.pbng.o: build/google/protobuf/timestamp.pbng.cc
	g++ -c $(CXX_OPTIONS) -o $@ $<

clean:
	rm -rf build
