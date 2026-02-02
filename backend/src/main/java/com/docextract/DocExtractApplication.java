package com.docextract;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class DocExtractApplication {

    public static void main(String[] args) {
        SpringApplication.run(DocExtractApplication.class, args);
        System.out.println("=================================");
        System.out.println("DocExtract Backend Started!");
        System.out.println("API Documentation: http://localhost:8080/api");
        System.out.println("=================================");
    }
}
