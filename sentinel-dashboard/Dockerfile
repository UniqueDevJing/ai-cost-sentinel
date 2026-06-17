FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

COPY target/sentinel-dashboard-*.jar app.jar

EXPOSE 9090

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
