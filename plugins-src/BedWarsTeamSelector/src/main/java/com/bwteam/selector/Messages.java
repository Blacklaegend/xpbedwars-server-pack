package com.bwteam.selector;

import org.bukkit.ChatColor;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Player;

import java.io.File;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

public final class Messages {

    private final TeamSelectorPlugin plugin;
    private YamlConfiguration yml;

    public Messages(TeamSelectorPlugin plugin) {
        this.plugin = plugin;
        reload();
    }

    public void reload() {
        File file = new File(plugin.getDataFolder(), "messages.yml");
        yml = YamlConfiguration.loadConfiguration(file);
        InputStream in = plugin.getResource("messages.yml");
        if (in != null) {
            yml.setDefaults(YamlConfiguration.loadConfiguration(new InputStreamReader(in, StandardCharsets.UTF_8)));
        }
    }

    public String raw(String path) {
        String value = yml.getString(path);
        return value == null ? path : value;
    }

    public String get(String path) {
        return color(raw(path));
    }

    public String format(String path, String... replacements) {
        String value = raw(path);
        for (int i = 0; i + 1 < replacements.length; i += 2) {
            value = value.replace("%" + replacements[i] + "%", replacements[i + 1]);
        }
        return color(value);
    }

    public List<String> list(String path) {
        List<String> result = new ArrayList<>();
        for (String line : yml.getStringList(path)) {
            result.add(color(line));
        }
        return result;
    }

    public void send(Player player, String path, String... replacements) {
        player.sendMessage(get("prefix") + format(path, replacements));
    }

    public static String color(String input) {
        return ChatColor.translateAlternateColorCodes('&', input == null ? "" : input);
    }
}
