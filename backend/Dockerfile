FROM maven:3.9-eclipse-temurin-17 AS build

WORKDIR /app

# 使用阿里云 Maven 镜像
RUN mkdir -p /root/.m2 && \
    echo '<?xml version="1.0" encoding="UTF-8"?>' > /root/.m2/settings.xml && \
    echo '<settings>' >> /root/.m2/settings.xml && \
    echo '  <mirrors>' >> /root/.m2/settings.xml && \
    echo '    <mirror>' >> /root/.m2/settings.xml && \
    echo '      <id>aliyunmaven</id>' >> /root/.m2/settings.xml && \
    echo '      <mirrorOf>central</mirrorOf>' >> /root/.m2/settings.xml && \
    echo '      <name>阿里云公共仓库</name>' >> /root/.m2/settings.xml && \
    echo '      <url>https://maven.aliyun.com/repository/public</url>' >> /root/.m2/settings.xml && \
    echo '    </mirror>' >> /root/.m2/settings.xml && \
    echo '  </mirrors>' >> /root/.m2/settings.xml && \
    echo '</settings>' >> /root/.m2/settings.xml

COPY pom.xml .
RUN mvn dependency:go-offline

COPY src ./src
RUN mvn clean package -DskipTests -Dmaven.repo.local=/root/.m2/repository

FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

COPY --from=build /app/target/docextract-backend-1.0.0.jar app.jar

RUN addgroup -S spring && adduser -S spring -G spring
USER spring:spring

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
