package com.costsentinel.controller;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

@RestController
@RequestMapping("/api")
public class ApiController {

    @Autowired
    private RestTemplate restTemplate;

    @GetMapping("/stats")
    public ResponseEntity<Map<String, Object>> stats(
            @RequestParam(defaultValue = "default") String project,
            @RequestParam(defaultValue = "30") int days) {
        Map<String, Object> result = restTemplate.getForObject(
                "/sentinel/stats?project=" + project + "&days=" + days, Map.class);
        return ResponseEntity.ok(result);
    }

    @GetMapping("/calls")
    public ResponseEntity<Map<String, Object>> calls(
            @RequestParam(defaultValue = "50") int limit) {
        Map<String, Object> result = restTemplate.getForObject(
                "/sentinel/calls?limit=" + limit, Map.class);
        return ResponseEntity.ok(result);
    }

    @GetMapping("/budget")
    public ResponseEntity<Map<String, Object>> budget(
            @RequestParam(defaultValue = "default") String project) {
        Map<String, Object> result = restTemplate.getForObject(
                "/sentinel/budget?project=" + project, Map.class);
        return ResponseEntity.ok(result);
    }

    @PostMapping("/budget")
    public ResponseEntity<Map<String, Object>> setBudget(
            @RequestParam(defaultValue = "default") String project,
            @RequestParam double daily,
            @RequestParam double monthly) {
        Map<String, Object> result = restTemplate.postForObject(
                "/sentinel/budget?project=" + project + "&daily=" + daily + "&monthly=" + monthly,
                null, Map.class);
        return ResponseEntity.ok(result);
    }
}
