#include <stdarg.h>
#include <stdlib.h>

#define EXPORT __attribute__((visibility("default"))) 

typedef void* BacklightStringHandle;

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
}
