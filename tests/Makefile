PROTOC := ../protoc-ng.py
PROTOC_OPTIONS := --all -I . --cpp_out build
PROTOC_OPTIONS_EXTRA :=
CXX_OPTIONS := -std=c++14 -I build -I ../extern/protozero/include -g

all: build/test

build/test: build/google/protobuf/timestamp.pbng.o \
	    build/thing/thing.pbng.o \
	    build/thing/ext.pbng.o \
	    build/thing/base.pbng.o \
	    build/thing/ext_base.pbng.o \
	    build/thing/containers.pbng.o \
	    build/thing/foreign.pbng.o \
	    build/main.o
	g++ -o build/test $^

build/main.o: main.cc
	g++ -c $(CXX_OPTIONS) -o $@ $<

build/thing/containers.pbng.cc: thing/containers.proto
	# Note, we need NG code-get for Google's proto. This file, descriptor.proto
	# can live in /usr/whatever as well as in ./google/.
	$(PROTOC) $(PROTOC_OPTIONS) $(PROTOC_OPTIONS_EXTRA) --all $<
build/thing/ext.pbng.cc: thing/ext.proto thing/thing.proto
	$(PROTOC) $(PROTOC_OPTIONS) $(PROTOC_OPTIONS_EXTRA) $<
build/thing/thing.pbng.cc: thing/thing.proto google/protobuf/timestamp.proto
	$(PROTOC) $(PROTOC_OPTIONS) $(PROTOC_OPTIONS_EXTRA) $<
build/thing/foreign.pbng.cc: thing/foreign.proto google/protobuf/timestamp.proto
	$(PROTOC) $(PROTOC_OPTIONS) $(PROTOC_OPTIONS_EXTRA) $<

build/thing/ext_base.pbng.cc: thing/ext_base.proto thing/base.proto
	$(PROTOC) $(PROTOC_OPTIONS) $(PROTOC_OPTIONS_EXTRA) $<
build/thing/base.pbng.cc: thing/base.proto
	$(PROTOC) $(PROTOC_OPTIONS) $(PROTOC_OPTIONS_EXTRA) $<

build/google/protobuf/timestamp.pbng.cc: google/protobuf/timestamp.proto
	$(PROTOC) $(PROTOC_OPTIONS) $(PROTOC_OPTIONS_EXTRA) $<

%.o: %.cc
	g++ -c $(CXX_OPTIONS) -o $@ $<

clean:
	rm -rf build
