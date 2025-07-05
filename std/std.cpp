#include <stdarg.h>
#include <stdlib.h>
#include "std.h"
#include <cstring>

#define EXPORT __attribute__((visibility("default"))) 

typedef void* P2StringHandle;

const char* P2String::c_str() const {
    return this->str.c_str();
}

size_t P2String::length() const {
    return strlen(this->str.c_str());
}



extern "C" {
    EXPORT char* create_string_array(int length, ...) {
        va_list args;
        va_start(args, length);

        char* chars = (char*)malloc(length + 1);
        if (!chars) {
            va_end(args);
            return NULL;
        }

        for (int i = 0; i < length; i++) {
            chars[i] = (char)va_arg(args, int);
        }

        va_end(args);
        chars[length] = '\0';

        return chars;
    }

    EXPORT P2StringHandle create_string(char* str) {
        P2String* p2string = new P2String(str);
        free(str);
        return p2string;
    }

    EXPORT const char* get_string_content(P2StringHandle handle) {
        return static_cast<P2String*>(handle)->c_str();
    }

    EXPORT size_t get_string_length(P2StringHandle handle) {
        return static_cast<P2String*>(handle)->length();
    }

    EXPORT void free_string(P2StringHandle handle){
        delete static_cast<P2String*>(handle);;
    }
}
