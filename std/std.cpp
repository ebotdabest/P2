#include <stdarg.h>
#include <string>
#include <cstring>
#include "std.h"

struct P2Vector {
    void* data;
    size_t elem_size;
    int capacity;
    size_t size;
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

    EXPORT char* __t__str__replace(char* self, char* old, char* replacement) {
        const char* pos = strstr(self, old);
            if (!pos) {
                char* result = (char*) malloc(strlen(self) + 1);
                if (!result) return NULL;
                strcpy(result, self);
                return result;
        }

        size_t len_before = pos - self;
        size_t len_to_replace = strlen(old);
        size_t len_replacement = strlen(replacement);
        size_t len_original = strlen(self);

        size_t new_len = len_before + len_replacement + (len_original - len_before - len_to_replace);
        char* result = (char*) malloc(new_len + 1);
        if (!result) return NULL;

        strncpy(result, self, len_before);
        strcpy(result + len_before, replacement);
        strcpy(result + len_before + len_replacement, pos + len_to_replace);

        return result;
    }
    //====================STRINGS======================
    
    //====================LISTS========================
    P2Vector* vector_init(size_t elm_size) {
        P2Vector* vector = (P2Vector*) malloc(sizeof(P2Vector));
        vector->elem_size = elm_size;
        vector->capacity = 10;
        vector->size = 0;
        vector->data = (void**) malloc(vector->capacity * sizeof(void*));

        return vector;
    }

    void vector_free(P2Vector* vector) {
        free(vector->data);
    }

    EXPORT void* vector_push_back(P2Vector* vector, void* value) {
        if (vector->size >= vector->capacity) {
            vector->capacity += 10;
            void* new_data = malloc(vector->capacity * vector->elem_size);

            memcpy(new_data, vector->data, vector->size * vector->elem_size);
            free(vector->data);
            vector->data = new_data;
        }

        char* base = (char*) vector->data;
        void* element_ptr = base + vector->size * vector->elem_size;
        memcpy(element_ptr, value, vector->elem_size);
        vector->size += 1;
        return value;
    }

    EXPORT void* vector_index(P2Vector* vector, int index) {
        void* element_ptr = (char*)vector->data + index * vector->elem_size;
        return element_ptr;
    }

    EXPORT size_t vector_size(P2Vector* vector) {
        return vector->size - 1;
    }

    EXPORT void* vector_insert_into(P2Vector* vector, void* value, int index) {
        char* base = (char*) vector->data;
        void* element_ptr = base + index * vector->elem_size;
        memcpy(element_ptr, value, vector->elem_size);
        vector->size += 1;
        return value;
    }
    //====================LISTS========================

    
}
