PROTOC := ../protoc-ng.py
CXX_OPTIONS := -std=c++14 -I build -g

all: build/test

build/test: build/thing/thing.pbng.o build/google/protobuf/timestamp.pbng.o build/main.o
	g++ -o build/test $^

build/main.o: main.cc
	g++ -c $(CXX_OPTIONS) -o $@ $<

build/thing/thing.pbng.cc: thing/thing.proto google/protobuf/timestamp.proto
	$(PROTOC) -I . --cpp_out build $<
build/google/protobuf/timestamp.pbng.cc: google/protobuf/timestamp.proto
	$(PROTOC) -I . --cpp_out build $<

build/thing/thing.pbng.o: build/thing/thing.pbng.cc build/google/protobuf/timestamp.pbng.cc
	g++ -c $(CXX_OPTIONS) -o $@ $<
build/google/protobuf/timestamp.pbng.o: build/google/protobuf/timestamp.pbng.cc
	g++ -c $(CXX_OPTIONS) -o $@ $<

clean:
	rm -rf build
