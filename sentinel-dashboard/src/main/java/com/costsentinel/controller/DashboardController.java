package com.costsentinel.controller;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

@Controller
public class DashboardController {

    @Autowired
    private RestTemplate restTemplate;

    @GetMapping("/")
    public String dashboard(Model model) {
        try {
            Map<String, Object> stats = restTemplate.getForObject(
                    "/sentinel/stats?project=default&days=30", Map.class);
            model.addAttribute("stats", stats);

            Map<String, Object> budget = restTemplate.getForObject(
                    "/sentinel/budget?project=default", Map.class);
            model.addAttribute("budget", budget);

            Map<String, Object> calls = restTemplate.getForObject(
                    "/sentinel/calls?limit=20", Map.class);
            model.addAttribute("calls", calls);

            Map<String, Object> health = restTemplate.getForObject(
                    "/sentinel/health", Map.class);
            model.addAttribute("health", health);

        } catch (Exception e) {
            model.addAttribute("error", "无法连接到 Sentinel 代理: " + e.getMessage());
        }
        return "dashboard";
    }
}
