package com.docextract;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

@SpringBootApplication
@EnableAsync
public class DocExtractApplication {

    public static void main(String[] args) {
        SpringApplication.run(DocExtractApplication.class, args);
    }
}
