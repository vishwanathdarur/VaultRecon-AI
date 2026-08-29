CXX = g++
CXXFLAGS = -std=c++17 -O2 -Wall -fPIC -Iinclude

# Find all cpp inside src recursively
SRC := $(shell find src -name '*.cpp')
OBJ := $(patsubst %.cpp, %.o, $(SRC))

all: $(OBJ) libminivaultdb.so

libminivaultdb.so: $(OBJ)
	$(CXX) -shared -o $@ $(OBJ)

# Compile .cpp → .o, creating directories if needed
%.o: %.cpp
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -c $< -o $@

# Build and run a specific test
test: $(OBJ)
	$(CXX) $(CXXFLAGS) $(OBJ) $(TEST) -o test.out
	./test.out

clean:
	rm -f $(OBJ) test.out libminivaultdb.so