package com.bwteam.selector;

import com.andrei1058.bedwars.api.BedWars;
import com.andrei1058.bedwars.api.arena.IArena;
import com.andrei1058.bedwars.api.party.Party;
import org.bukkit.Bukkit;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Player;
import org.bukkit.plugin.RegisteredServiceProvider;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * BedWars1058 team selector for Paper 1.21.x.
 */
public final class TeamSelectorPlugin extends JavaPlugin {

    private BedWars api;
    private Messages messages;
    private SelectionStore store;
    private PartyManager parties;
    private PreferenceAssigner assigner;
    private boolean assigning;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        saveResource("messages.yml", false);

        messages = new Messages(this);
        store = new SelectionStore();
        parties = new PartyManager(this);
        assigner = new PreferenceAssigner(this);

        RegisteredServiceProvider<BedWars> rsp = Bukkit.getServicesManager().getRegistration(BedWars.class);
        if (rsp == null) {
            getLogger().severe("没有找到 BedWars1058 的 API 服务，请确认 BedWars1058 已安装并成功启动。");
            Bukkit.getPluginManager().disablePlugin(this);
            return;
        }
        api = rsp.getProvider();

        for (IArena arena : api.getArenaUtil().getArenas()) {
            arena.setTeamAssigner(assigner);
        }

        Bukkit.getPluginManager().registerEvents(new PlayerListener(this), this);

        SelectCommand command = new SelectCommand(this);
        if (getCommand("bwteam") != null) {
            getCommand("bwteam").setExecutor(command);
            getCommand("bwteam").setTabCompleter(command);
        } else {
            getLogger().warning("plugin.yml 中没有注册 /bwteam 命令。");
        }

        PartyCommand partyCommand = new PartyCommand(this);
        if (getCommand("zd") != null) {
            getCommand("zd").setExecutor(partyCommand);
            getCommand("zd").setTabCompleter(partyCommand);
        } else {
            getLogger().warning("plugin.yml 中没有注册 /zd 命令。");
        }

        warnIfAssignerDisabled();
        getLogger().info("BedWarsTeamSelector v" + getDescription().getVersion() + " 已启用，等待大厅队伍选择器就绪。");
    }

    @Override
    public void onDisable() {
        if (store != null) {
            store.clearAll();
        }
    }

    /**
     * BedWars1058 默认 experimental-team-assigner: true。
     * 如果服主手动关掉了，我们只能用 TeamAssignEvent 兜底（组队会失效），这里明确警告。
     */
    private void warnIfAssignerDisabled() {
        if (!getConfig().getBoolean("warn-if-assigner-disabled", true)) {
            return;
        }
        File file = new File(getDataFolder().getParentFile(), "BedWars1058" + File.separator + "config.yml");
        if (!file.isFile()) {
            return;
        }
        YamlConfiguration yml = YamlConfiguration.loadConfiguration(file);
        if (!yml.getBoolean("experimental-team-assigner", true)) {
            getLogger().warning("BedWars1058 的 experimental-team-assigner 为 false，");
            getLogger().warning("队伍选择将退回 TeamAssignEvent 兜底模式：单人可用，组队跟随会失效。");
            getLogger().warning("建议在 BedWars1058/config.yml 中把它改回 true 后重启服务器。");
        }
    }

    public BedWars api() {
        return api;
    }

    public Party party() {
        return api == null ? null : api.getPartyUtil();
    }

    public Messages messages() {
        return messages;
    }

    public SelectionStore store() {
        return store;
    }

    public PartyManager parties() {
        return parties;
    }

    public PreferenceAssigner assigner() {
        return assigner;
    }

    public boolean inAnyParty(Player player) {
        Party bedwarsParty = party();
        return parties.inParty(player.getUniqueId())
                || (bedwarsParty != null && bedwarsParty.hasParty(player));
    }

    public boolean isAnyOwner(Player player) {
        Party bedwarsParty = party();
        return parties.isOwner(player.getUniqueId())
                || (bedwarsParty != null && bedwarsParty.hasParty(player) && bedwarsParty.isOwner(player));
    }

    /**
     * Party members (leader included) that are currently waiting in this arena.
     * Our /zd party wins over the BedWars1058 party. Returns an empty list when the
     * player is not a party owner.
     */
    public List<Player> partyGroup(Player leader, IArena arena) {
        List<Player> group = new ArrayList<>();
        if (parties.inParty(leader.getUniqueId())) {
            if (!parties.isOwner(leader.getUniqueId())) {
                return group;
            }
            for (UUID id : parties.membersOf(leader.getUniqueId())) {
                Player member = Bukkit.getPlayer(id);
                if (member != null && member.isOnline() && arena.isPlayer(member) && !arena.isSpectator(member)) {
                    group.add(member);
                }
            }
            return group;
        }
        Party bedwarsParty = party();
        if (bedwarsParty != null && bedwarsParty.hasParty(leader) && bedwarsParty.isOwner(leader)) {
            List<Player> members = bedwarsParty.getMembers(leader);
            if (members != null) {
                for (Player member : members) {
                    if (member != null && member.isOnline() && arena.isPlayer(member) && !arena.isSpectator(member)) {
                        group.add(member);
                    }
                }
            }
        }
        return group;
    }

    public boolean isAssigning() {
        return assigning;
    }

    public void setAssigning(boolean assigning) {
        this.assigning = assigning;
    }

    public int lockSeconds() {
        return getConfig().getInt("lock-seconds", 10);
    }
}
