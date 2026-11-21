#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void) {
    char *mem = malloc(32);

    if (mem == NULL)
        return 1;

    strcpy(mem, "DCC");

    printf("%s\n", mem);

    free(mem);
    return 0;
}
