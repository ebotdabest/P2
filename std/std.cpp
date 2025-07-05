#include <stdarg.h>
#include <stdlib.h>
#include "std.h"
#include <cstring>

#define EXPORT __attribute__((visibility("default"))) 

extern "C" {
    // ===================STRINGS======================
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
    
    EXPORT void free_string(char* str) {
        free(str);
    }
    
    EXPORT size_t string_length(char* str) {
        return strlen(str);
    }

    
    //====================STRINGS======================
}
