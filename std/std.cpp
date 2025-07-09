#include <stdarg.h>
#include <stdlib.h>
#include "std.h"
#include <cstring>
#include <stdio.h>

#define EXPORT __attribute__((visibility("default"))) 

struct P2File {
    char* filename;
    char* mode;
    FILE* file_ptr;
};

extern "C" {
    // ===================STRINGS======================
    EXPORT char* create_string_array(int length, ...) {
        va_list args;
        va_start(args, length);
        
        char* chars = (char*) malloc(length + 1);
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
    
    EXPORT void __t__str__free(char* str) {
        free(str);
    }
    
    EXPORT size_t string_length(char* str) {
        return strlen(str);
    }

    EXPORT bool __t__str__eq__(char* str1, char* str2) {
        return strcmp(str1, str2) == 0;
    }
    //====================STRINGS======================

    EXPORT P2File* open(char* filename, char* mode) {
        P2File* file = (P2File*) malloc(sizeof(P2File));
        if (!file) {
            return NULL;
        }
        file->filename = filename;
        file->mode = mode;
        file->file_ptr = fopen(filename, mode);
        
        return file;
    }

    EXPORT char* read_file(P2File* file) {
        
        fseek(file->file_ptr, 0, SEEK_END);
        long size = ftell(file->file_ptr);
        rewind(file->file_ptr);
        char* content = (char*) malloc(size + 1);

        size_t read_size = fread(content, 1, size, file->file_ptr);
        content[read_size] = '\0';
        return content;
    }

    EXPORT void __t__file__close(P2File* file) {
        fclose(file->file_ptr);
        free(file);
    }
}
