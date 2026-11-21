package com.andrei1058.bedwars.support.version;

import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.entity.Player;

/**
 * Bukkit-only replacement for the 1.21.4 broken ClientboundLevelParticlesPacket call.
 * Shows the redstone marker above a player carrying TNT to all other players in the world.
 */
public final class ParticleFix {

    private ParticleFix() {
    }

    public static void playRedstone(Player player) {
        if (player == null) return;
        Location loc = player.getLocation().clone().add(0.0, 2.6, 0.0);
        Particle.DustOptions dust = new Particle.DustOptions(Color.RED, 1.0F);
        for (Player other : player.getWorld().getPlayers()) {
            if (other.equals(player)) continue;
            other.spawnParticle(Particle.DUST, loc, 1, 0.0, 0.0, 0.0, 0.0, dust);
        }
    }
}
