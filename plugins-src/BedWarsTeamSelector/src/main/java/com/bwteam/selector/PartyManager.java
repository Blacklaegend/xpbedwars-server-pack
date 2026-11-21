package com.bwteam.selector;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * /zd party system. UUID based so it survives relog within one server session.
 */
public final class PartyManager {

    public static final class Party {
        private UUID owner;
        private final LinkedHashSet<UUID> members = new LinkedHashSet<>();
    }

    public static final class Invite {
        public final UUID inviter;
        public final long expiresAt;

        Invite(UUID inviter, long expiresAt) {
            this.inviter = inviter;
            this.expiresAt = expiresAt;
        }
    }

    private final TeamSelectorPlugin plugin;
    private final Map<UUID, Party> byMember = new ConcurrentHashMap<>();
    private final Map<UUID, Invite> invites = new ConcurrentHashMap<>();

    public PartyManager(TeamSelectorPlugin plugin) {
        this.plugin = plugin;
    }

    public boolean inParty(UUID id) {
        return byMember.containsKey(id);
    }

    public boolean isOwner(UUID id) {
        Party party = byMember.get(id);
        return party != null && party.owner.equals(id);
    }

    public UUID ownerOf(UUID id) {
        Party party = byMember.get(id);
        return party == null ? null : party.owner;
    }

    public int size(UUID id) {
        Party party = byMember.get(id);
        return party == null ? 0 : party.members.size();
    }

    public List<UUID> membersOf(UUID id) {
        Party party = byMember.get(id);
        return party == null ? List.of() : new ArrayList<>(party.members);
    }

    public void create(UUID owner) {
        Party party = new Party();
        party.owner = owner;
        party.members.add(owner);
        byMember.put(owner, party);
    }

    public void invite(UUID from, UUID to) {
        long seconds = plugin.getConfig().getLong("party.invite-expire-seconds", 60L);
        invites.put(to, new Invite(from, System.currentTimeMillis() + seconds * 1000L));
    }

    public Invite pendingInvite(UUID to) {
        Invite invite = invites.get(to);
        if (invite == null) {
            return null;
        }
        if (invite.expiresAt < System.currentTimeMillis()) {
            invites.remove(to);
            return null;
        }
        return invite;
    }

    public void clearInvite(UUID to) {
        invites.remove(to);
    }

    /**
     * @return false when the party no longer exists
     */
    public boolean join(UUID joiner, UUID owner) {
        Party party = byMember.get(owner);
        if (party == null || !party.owner.equals(owner)) {
            return false;
        }
        if (party.members.contains(joiner)) {
            return true;
        }
        leave(joiner);
        party.members.add(joiner);
        byMember.put(joiner, party);
        return true;
    }

    public boolean leave(UUID member) {
        Party party = byMember.get(member);
        if (party == null || party.owner.equals(member)) {
            return false;
        }
        party.members.remove(member);
        byMember.remove(member);
        if (party.members.size() <= 1) {
            // nobody left except the owner: keep the owner's solo party, it still works as a party of one
            return true;
        }
        return true;
    }

    public boolean promote(UUID owner, UUID target) {
        Party party = byMember.get(owner);
        if (party == null || !party.owner.equals(owner) || !party.members.contains(target) || target.equals(owner)) {
            return false;
        }
        party.owner = target;
        return true;
    }

    public boolean remove(UUID owner, UUID target) {
        Party party = byMember.get(owner);
        if (party == null || !party.owner.equals(owner) || target.equals(owner) || !party.members.contains(target)) {
            return false;
        }
        party.members.remove(target);
        byMember.remove(target);
        return true;
    }

    public List<UUID> disband(UUID owner) {
        Party party = byMember.get(owner);
        if (party == null || !party.owner.equals(owner)) {
            return List.of();
        }
        List<UUID> members = new ArrayList<>(party.members);
        for (UUID member : members) {
            byMember.remove(member);
        }
        return members;
    }

    /**
     * Owner disbands, member leaves, invite is dropped.
     */
    public void onQuit(UUID id) {
        if (isOwner(id)) {
            disband(id);
        } else {
            leave(id);
        }
        clearInvite(id);
    }

    public static Player player(UUID id) {
        return Bukkit.getPlayer(id);
    }
}
