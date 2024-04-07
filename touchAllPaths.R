require(tidyverse)

argv=commandArgs(trailing=T)

paths=scan(argv[1],"",sep="\n")

for(pi in paths) {

    cat("creating",pi,"...")
    dir=gsub("^/","",dirname(pi))
    base=basename(pi)
    fs::dir_create(dir)
    fs::file_touch(file.path(dir,base))
    cat("\n")
}

