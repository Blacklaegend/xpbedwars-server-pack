package com.andrei1058.bedwars.shop.listeners;

import com.andrei1058.bedwars.api.arena.shop.IBuyItem;
import com.andrei1058.bedwars.api.arena.shop.IContentTier;
import com.andrei1058.bedwars.shop.ShopCache;
import com.andrei1058.bedwars.shop.main.CategoryContent;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

import java.util.List;

/**
 * Shift + right click buys one full stack of a stackable shop item.
 * Shift + left click keeps the vanilla BedWars quick-buy behavior.
 */
public final class StackBuy {

    private StackBuy() {
    }

    public static void buy(Player player, CategoryContent content, ShopCache cache, int slot) {
        if (player == null || content == null || cache == null) return;
        try {
            List<IContentTier> tiers = content.getContentTiers();
            if (tiers == null || tiers.isEmpty()) {
                content.execute(player, cache, slot);
                return;
            }
            int tierNo = cache.getContentTier(content.getIdentifier());
            int index = Math.min(Math.max(tierNo - 1, 0), tiers.size() - 1);
            IContentTier tier = tiers.get(index);
            if (tier == null) {
                content.execute(player, cache, slot);
                return;
            }

            int perPurchase = 0;
            Material material = null;
            for (IBuyItem buyItem : tier.getBuyItemsList()) {
                if (buyItem == null || buyItem.getItemStack() == null) continue;
                ItemStack stack = buyItem.getItemStack();
                perPurchase = stack.getAmount();
                material = stack.getType();
                break;
            }
            if (perPurchase <= 0 || material == null) {
                content.execute(player, cache, slot);
                return;
            }
            int maxStack = Math.max(1, material.getMaxStackSize());
            if (maxStack <= 1 || perPurchase >= maxStack) {
                content.execute(player, cache, slot);
                return;
            }

            int purchases = maxStack / perPurchase;
            int price = tier.getPrice();
            Material currency = tier.getCurrency();
            for (int i = 0; i < purchases; i++) {
                if (CategoryContent.calculateMoney(player, currency) < price) break;
                if (player.getInventory().firstEmpty() < 0) break;
                content.execute(player, cache, slot);
            }
        } catch (Throwable t) {
            content.execute(player, cache, slot);
        }
    }
}
