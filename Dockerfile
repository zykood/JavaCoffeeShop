FROM maven:latest
RUN mkdir /usr/src/project
COPY . /usr/src/project
WORKDIR /usr/src/project
RUN mvn package -DskipTests
CMD mvn spring-boot:run
EXPOSE 8081
