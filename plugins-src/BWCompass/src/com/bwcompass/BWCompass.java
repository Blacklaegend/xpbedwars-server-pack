package com.bwcompass;

import com.andrei1058.bedwars.api.BedWars;
import com.andrei1058.bedwars.api.arena.GameState;
import com.andrei1058.bedwars.api.arena.IArena;
import com.andrei1058.bedwars.api.arena.team.ITeam;
import com.andrei1058.bedwars.api.events.shop.ShopBuyEvent;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.entity.Player;
import org.bukkit.Location;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.CompassMeta;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.plugin.java.JavaPlugin;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * BedWars1058 compass:
 *  - placed in the second-to-last hotbar slot (slot index 7)
 *  - tracking is automatic: the nearest enemy is locked every 0.5s and shown on the action bar
 *  - shift + right click opens quick team messages, including a resource request submenu
 *
 * 233BedWars's ActionBar addon is disabled in its config (addons.ActionBar: false), so the
 * "home distance" line no longer fights with this one.
 */
public class BWCompass extends JavaPlugin implements Listener {

    private static final int COMPASS_SLOT = 7;
    private static final List<String> QUICK_MESSAGES = Arrays.asList(
            "\u00a7c\u654c\u4eba\u5728\u8fd9\u91cc\uff01",
            "\u00a7e\u9700\u8981\u652f\u63f4\uff01",
            "\u00a76\u4e00\u8d77\u6253\u5e8a\uff01",
            "\u00a7b\u64a4\u9000\uff01",
            "\u00a7a\u8d44\u6e90\u70b9\u96c6\u5408",
            "\u00a7c\u901f\u901f\u56de\u5bb6\uff01");

    private static final String[] RESOURCE_NAMES = {"\u94c1", "\u91d1", "\u94bb\u77f3", "\u7eff\u5b9d\u77f3"};
    private static final Material[] RESOURCE_MATERIALS = {
            Material.IRON_INGOT, Material.GOLD_INGOT, Material.DIAMOND, Material.EMERALD};

    private BedWars api;
    private NamespacedKey compassKey;
    private final Set<UUID> wasHolding = new HashSet<>();

    @Override
    public void onEnable() {
        try {
            api = Bukkit.getServicesManager().getRegistration(BedWars.class).getProvider();
        } catch (Exception e) {
            getLogger().severe("BedWars1058 API not found, disabling.");
            getServer().getPluginManager().disablePlugin(this);
            return;
        }
        compassKey = new NamespacedKey(this, "compass");

        Bukkit.getPluginManager().registerEvents(this, this);
        Bukkit.getScheduler().runTaskTimer(this, this::giveCompasses, 40L, 40L);
        Bukkit.getScheduler().runTaskTimer(this, this::updateTracking, 10L, 2L);
        getLogger().info("BWCompass enabled");
    }

    // ------------------------------------------------------------------ compass item

    private ItemStack createCompass() {
        ItemStack item = new ItemStack(Material.COMPASS);
        ItemMeta meta = item.getItemMeta();
        if (meta != null) {
            meta.setDisplayName("\u00a7a\u6307\u5357\u9488 \u00a77\u81ea\u52a8\u9501\u5b9a\u6700\u8fd1\u654c\u4eba");
            meta.setLore(Arrays.asList(
                    "\u00a77\u81ea\u52a8\u8ffd\u8e2a\u6700\u8fd1\u7684\u654c\u4eba",
                    "\u00a77Shift+\u53f3\u952e: \u5feb\u6377\u6d88\u606f",
                    "\u00a78\u5b9e\u65f6\u8ddd\u79bb\u663e\u793a\u5728\u4e0b\u65b9\u72b6\u6001\u680f"));
            meta.getPersistentDataContainer().set(compassKey, PersistentDataType.BYTE, (byte) 1);
            item.setItemMeta(meta);
        }
        return item;
    }

    private boolean isCompass(ItemStack item) {
        if (item == null || item.getType() != Material.COMPASS || !item.hasItemMeta()) return false;
        ItemMeta meta = item.getItemMeta();
        return meta != null && meta.getPersistentDataContainer().has(compassKey, PersistentDataType.BYTE);
    }

    private void giveCompasses() {
        for (Player player : Bukkit.getOnlinePlayers()) {
            if (!isInGame(player)) continue;
            if (isCompass(player.getInventory().getItem(COMPASS_SLOT))) continue;
            for (int i = 0; i < player.getInventory().getSize(); i++) {
                if (i != COMPASS_SLOT && isCompass(player.getInventory().getItem(i))) {
                    player.getInventory().setItem(i, null);
                }
            }
            ItemStack current = player.getInventory().getItem(COMPASS_SLOT);
            if (current == null || current.getType() == Material.AIR) {
                player.getInventory().setItem(COMPASS_SLOT, createCompass());
            } else if (current.getType() == Material.COMPASS) {
                // BedWars puts its own tracker compass there; replace it with ours so the
                // player always holds the compass whose target we update.
                player.getInventory().setItem(COMPASS_SLOT, createCompass());
            } else {
                player.getInventory().addItem(createCompass());
            }
        }
    }

    private boolean isInGame(Player player) {
        IArena arena = api.getArenaUtil().getArenaByPlayer(player);
        return arena != null
                && arena.getStatus() == GameState.playing
                && arena.isPlayer(player)
                && !arena.isSpectator(player);
    }

    // ------------------------------------------------------------------ interaction (quick messages only)

    @EventHandler
    public void onInteract(PlayerInteractEvent event) {
        if (event.getAction() != org.bukkit.event.block.Action.RIGHT_CLICK_AIR
                && event.getAction() != org.bukkit.event.block.Action.RIGHT_CLICK_BLOCK) return;
        if (!isCompass(event.getItem())) return;
        Player player = event.getPlayer();
        if (!isInGame(player)) return;
        event.setCancelled(true);
        if (player.isSneaking()) {
            openQuickMenu(player);
        }
    }

    @EventHandler
    public void onDeath(PlayerDeathEvent event) {
        // nothing to clean up: tracking is automatic
    }

    // ------------------------------------------------------------------ armor guard
    // BedWars' internal weight cache is not reliable for armor because armor is lost on
    // death; this listener enforces the rule directly from the armor the player wears.
    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onShopBuy(ShopBuyEvent event) {
        Player player = event.getBuyer();
        if (player == null || !isInGame(player)) return;
        String id = event.getCategoryContent().getIdentifier().toLowerCase();
        if (!id.contains("armor") && !id.contains("chainmail")) return;
        int want = armorTierFromId(id);
        if (want <= 0) return;
        if (currentArmorTier(player) >= want) {
            event.setCancelled(true);
            player.sendMessage("\u00a7c\u4f60\u5df2\u7ecf\u62e5\u6709\u540c\u7b49\u7ea7\u6216\u66f4\u9ad8\u7ea7\u7684\u62a4\u7532\uff0c\u4e0d\u80fd\u91cd\u590d\u8d2d\u4e70\uff01");
        }
    }

    private int armorTierFromId(String id) {
        if (id.contains("netherite")) return 4;
        if (id.contains("diamond")) return 3;
        if (id.contains("iron")) return 2;
        if (id.contains("chainmail")) return 1;
        return 0;
    }

    private int currentArmorTier(Player player) {
        int tier = 0;
        // worn armor plus anything carried: if BedWars did not auto-equip (team leather
        // armor can stay in the slot), the purchased set is still in the inventory.
        for (ItemStack item : player.getInventory().getArmorContents()) {
            tier = Math.max(tier, armorTier(item));
        }
        for (ItemStack item : player.getInventory().getContents()) {
            tier = Math.max(tier, armorTier(item));
        }
        return tier;
    }

    private int armorTier(ItemStack item) {
        if (item == null) return 0;
        String name = item.getType().name();
        if (!name.endsWith("_BOOTS") && !name.endsWith("_LEGGINGS")
                && !name.endsWith("_CHESTPLATE") && !name.endsWith("_HELMET")) {
            return 0;
        }
        if (name.startsWith("NETHERITE_")) return 4;
        if (name.startsWith("DIAMOND_")) return 3;
        if (name.startsWith("IRON_")) return 2;
        if (name.startsWith("CHAINMAIL_")) return 1;
        return 0;
    }

    // ------------------------------------------------------------------ automatic tracking

    private void updateTracking() {
        for (Player player : new ArrayList<>(Bukkit.getOnlinePlayers())) {
            if (player.isDead() || !isInGame(player)) continue;
            IArena arena = api.getArenaUtil().getArenaByPlayer(player);
            if (arena == null) continue;
            Player target = nearestEnemy(arena, player);
            if (target == null) {
                if (holdingCompass(player)) {
                    player.sendActionBar("\u00a77\u9644\u8fd1\u6ca1\u6709\u654c\u4eba");
                }
                continue;
            }
            // Always keep the compass target on the enemy, even when the compass is not
            // in hand yet. The action bar distance is only shown while holding it.
            player.setCompassTarget(target.getLocation());
            if (!holdingCompass(player)) {
                if (wasHolding.remove(player.getUniqueId())) {
                    player.sendActionBar("");
                }
                continue;
            }
            wasHolding.add(player.getUniqueId());
            updateLodestone(player, target);
            double distance = player.getLocation().distance(target.getLocation());
            player.sendActionBar("\u00a7e\u8ffd\u8e2a: \u00a7f" + target.getName()
                    + " \u00a77| \u00a7f" + String.format("%.1f", distance) + "m");
        }
    }

    private boolean holdingCompass(Player player) {
        // main hand only: a compass parked in the offhand must not keep the distance line visible
        return player.getInventory().getItemInMainHand().getType() == Material.COMPASS;
    }

    private void updateLodestone(Player player, Player target) {
        ItemStack item = player.getInventory().getItemInMainHand();
        if (item == null || item.getType() != Material.COMPASS || item.getItemMeta() == null) return;
        ItemMeta meta = item.getItemMeta();
        if (!(meta instanceof CompassMeta)) return;
        CompassMeta compass = (CompassMeta) meta;
        Location loc = target.getLocation();
        Location old = compass.getLodestone();
        if (old != null && old.getWorld() != null && old.getWorld().equals(loc.getWorld())
                && old.distanceSquared(loc) < 4.0) {
            return;
        }
        compass.setLodestone(loc);
        compass.setLodestoneTracked(false);
        item.setItemMeta(compass);
        player.getInventory().setItemInMainHand(item);
    }

    private Player nearestEnemy(IArena arena, Player player) {
        ITeam ownTeam = arena.getTeam(player);
        Player best = null;
        double bestDistance = Double.MAX_VALUE;
        for (Player other : arena.getPlayers()) {
            if (other == null || other.equals(player)) continue;
            if (other.isDead() || other.getHealth() <= 0) continue;
            if (!other.getWorld().equals(player.getWorld())) continue;
            if (arena.isSpectator(other) || arena.isReSpawning(other)) continue;
            ITeam otherTeam = arena.getTeam(other);
            if (otherTeam == null || otherTeam.equals(ownTeam)) continue;
            double distance = player.getLocation().distanceSquared(other.getLocation());
            if (distance < bestDistance) {
                bestDistance = distance;
                best = other;
            }
        }
        return best;
    }

    // ------------------------------------------------------------------ quick messages

    private void openQuickMenu(Player player) {
        QuickHolder holder = new QuickHolder();
        Inventory inventory = Bukkit.createInventory(holder, 27, "\u00a78\u5feb\u6377\u6d88\u606f");
        holder.setInventory(inventory);

        Material[] materials = {Material.RED_DYE, Material.GOLD_INGOT, Material.DIAMOND_PICKAXE,
                Material.FEATHER, Material.EMERALD, Material.RED_BED};
        int[] slots = {10, 11, 12, 13, 14, 15};
        for (int i = 0; i < QUICK_MESSAGES.size(); i++) {
            inventory.setItem(slots[i], button(materials[i], QUICK_MESSAGES.get(i),
                    "\u00a77\u70b9\u51fb\u53d1\u9001\u7ed9\u961f\u53cb"));
        }
        inventory.setItem(16, button(Material.CHEST, "\u00a7e\u6211\u9700\u8981\u8d44\u6e90...",
                "\u00a77\u9009\u62e9\u4f60\u9700\u8981\u7684\u8d44\u6e90"));
        player.openInventory(inventory);
    }

    private void openResourceMenu(Player player) {
        ResourceHolder holder = new ResourceHolder();
        Inventory inventory = Bukkit.createInventory(holder, 27, "\u00a78\u9009\u62e9\u8d44\u6e90");
        holder.setInventory(inventory);
        int[] slots = {10, 12, 14, 16};
        for (int i = 0; i < RESOURCE_NAMES.length; i++) {
            inventory.setItem(slots[i], button(RESOURCE_MATERIALS[i],
                    "\u00a7f\u6211\u9700\u8981" + RESOURCE_NAMES[i],
                    "\u00a77\u70b9\u51fb\u53d1\u9001\u7ed9\u961f\u53cb"));
        }
        inventory.setItem(26, button(Material.ARROW, "\u00a77\u8fd4\u56de", "\u00a77\u56de\u5230\u5feb\u6377\u6d88\u606f"));
        player.openInventory(inventory);
    }

    private ItemStack button(Material material, String name, String lore) {
        ItemStack item = new ItemStack(material);
        ItemMeta meta = item.getItemMeta();
        if (meta != null) {
            meta.setDisplayName(name);
            meta.setLore(Arrays.asList(lore));
            item.setItemMeta(meta);
        }
        return item;
    }

    @EventHandler
    public void onQuickClick(InventoryClickEvent event) {
        if (!(event.getWhoClicked() instanceof Player)) return;
        Player player = (Player) event.getWhoClicked();
        InventoryHolder holder = event.getInventory().getHolder();

        if (holder instanceof QuickHolder) {
            event.setCancelled(true);
            int slot = event.getSlot();
            if (slot == 16) {
                openResourceMenu(player);
                return;
            }
            int index = indexOf(slot, new int[]{10, 11, 12, 13, 14, 15});
            if (index < 0) return;
            sendTeamMessage(player, QUICK_MESSAGES.get(index));
            player.closeInventory();
            return;
        }

        if (holder instanceof ResourceHolder) {
            event.setCancelled(true);
            int slot = event.getSlot();
            if (slot == 26) {
                openQuickMenu(player);
                return;
            }
            int index = indexOf(slot, new int[]{10, 12, 14, 16});
            if (index < 0) return;
            sendTeamMessage(player, "\u00a7e\u6211\u9700\u8981" + RESOURCE_NAMES[index] + "\uff01");
            player.closeInventory();
        }
    }

    private int indexOf(int slot, int[] slots) {
        for (int i = 0; i < slots.length; i++) {
            if (slots[i] == slot) return i;
        }
        return -1;
    }

    private void sendTeamMessage(Player player, String message) {
        IArena arena = api.getArenaUtil().getArenaByPlayer(player);
        if (arena == null) return;
        ITeam team = arena.getTeam(player);
        if (team == null) return;
        for (Player member : team.getMembers()) {
            if (member != null && member.isOnline()) {
                member.sendMessage("\u00a78[\u00a7b\u5feb\u6377\u00a78] \u00a7f" + player.getName() + "\u00a77: " + message);
            }
        }
    }

    private static final class QuickHolder implements InventoryHolder {
        private Inventory inventory;

        void setInventory(Inventory inventory) {
            this.inventory = inventory;
        }

        @Override
        public Inventory getInventory() {
            return inventory;
        }
    }

    private static final class ResourceHolder implements InventoryHolder {
        private Inventory inventory;

        void setInventory(Inventory inventory) {
            this.inventory = inventory;
        }

        @Override
        public Inventory getInventory() {
            return inventory;
        }
    }
}
