package com.docextract.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Response<T> {
    private Integer code;
    private String message;
    private T data;

    public static <T> Response<T> success(T data) {
        return Response.<T>builder()
                .code(200)
                .message("操作成功")
                .data(data)
                .build();
    }

    public static <T> Response<T> success(String message, T data) {
        return Response.<T>builder()
                .code(200)
                .message(message)
                .data(data)
                .build();
    }

    public static <T> Response<T> error(String message) {
        return Response.<T>builder()
                .code(500)
                .message(message)
                .data(null)
                .build();
    }

    public static <T> Response<T> error(Integer code, String message) {
        return Response.<T>builder()
                .code(code)
                .message(message)
                .data(null)
                .build();
    }
}
