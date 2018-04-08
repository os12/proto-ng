PROTOC := ../protoc-ng.py
PROTOC_OPTIONS := --all -I . --cpp_out build
PROTOC_OPTIONS_EXTRA :=
CXX_OPTIONS := -std=c++14 -I build -g

all: build/test

build/test: build/thing/thing.pbng.o \
	    build/thing/ext.pbng.o \
	    build/google/protobuf/timestamp.pbng.o \
	    build/main.o
	g++ -o build/test $^

build/main.o: main.cc
	g++ -c $(CXX_OPTIONS) -o $@ $<

build/thing/ext.pbng.cc: thing/ext.proto thing/thing.proto
	$(PROTOC) $(PROTOC_OPTIONS) $(PROTOC_OPTIONS_EXTRA) $<
build/thing/thing.pbng.cc: thing/thing.proto google/protobuf/timestamp.proto
	$(PROTOC) $(PROTOC_OPTIONS) $(PROTOC_OPTIONS_EXTRA) $<
build/google/protobuf/timestamp.pbng.cc: google/protobuf/timestamp.proto
	$(PROTOC) $(PROTOC_OPTIONS) $(PROTOC_OPTIONS_EXTRA) $<

%.o: %.cc
	g++ -c $(CXX_OPTIONS) -o $@ $<

clean:
	rm -rf build
