'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Users, Plus, Loader2, ShieldAlert } from 'lucide-react';
import { getOrganizations, getTeams, getTeamMembers } from '@/lib/api/organizations';
import { useBilling } from '@/lib/hooks/useBilling';
import { SkeletonTable } from '@/components/ui/SkeletonCard';
import { EmptyState } from '@/components/ui/EmptyState';
import { toast } from 'sonner';

export default function TeamSettingsPage() {
    const { data: billing } = useBilling();
    const plan = billing?.plan ?? 'free';

    // 1. Get orgs
    const { data: orgData, isLoading: isLoadingOrgs } = useQuery({
        queryKey: ['orgs'],
        queryFn: getOrganizations,
    });

    const firstOrgId = orgData?.organizations?.[0]?.id;

    // 2. Get teams for that org
    const { data: teamsData, isLoading: isLoadingTeams } = useQuery({
        queryKey: ['orgs', firstOrgId, 'teams'],
        queryFn: () => getTeams(firstOrgId!),
        enabled: !!firstOrgId,
    });

    const firstTeamId = teamsData?.teams?.[0]?.id;

    // 3. Get members
    const { data: membersData, isLoading: isLoadingMembers } = useQuery({
        queryKey: ['orgs', firstOrgId, 'teams', firstTeamId, 'members'],
        queryFn: () => getTeamMembers(firstOrgId!, firstTeamId!),
        enabled: !!firstOrgId && !!firstTeamId,
    });

    const isLoading = isLoadingOrgs || isLoadingTeams || isLoadingMembers;
    const members = membersData?.members ?? [];

    const handleInviteClick = () => {
        if (plan === 'free') {
            toast.error('Upgrade Required', {
                description: 'Team management is only available on Pro and Enterprise plans.',
                icon: <ShieldAlert className="w-4 h-4 text-sev-critical" />,
            });
            return;
        }
        toast.info('Invite flow would open here.');
    };

    return (
        <div className="space-y-6 max-w-4xl">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-xl font-bold text-text-1">Team Members</h1>
                    <p className="text-sm text-text-3 mt-1">Manage who has access to your organization.</p>
                </div>
                <button
                    onClick={handleInviteClick}
                    className="h-9 px-4 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-light transition-colors flex items-center gap-2"
                >
                    <Plus className="w-4 h-4" /> Invite Member
                </button>
            </div>

            {/* List */}
            {isLoading ? (
                <SkeletonTable rows={5} />
            ) : members.length === 0 ? (
                <EmptyState
                    icon={Users}
                    title="No members found"
                    description="You don't have any members in your team yet."
                />
            ) : (
                <div className="bg-bg-card border border-border rounded-xl overflow-hidden shadow-sm">
                    <table className="w-full text-left text-sm whitespace-nowrap">
                        <thead className="bg-bg-card-2 border-b border-border text-text-3">
                            <tr>
                                <th className="px-4 py-3 font-medium">Member</th>
                                <th className="px-4 py-3 font-medium">Role</th>
                                <th className="px-4 py-3 font-medium">Joined</th>
                                <th className="px-4 py-3 font-medium w-32"></th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-border/50">
                            {members.map((m) => (
                                <tr key={m.id} className="hover:bg-bg-card-2/50 transition-colors">
                                    <td className="px-4 py-3">
                                        <div className="flex items-center gap-3">
                                            <div className="w-8 h-8 rounded-full bg-brand-dim text-brand-light flex items-center justify-center font-medium shrink-0">
                                                {m.user?.name?.charAt(0)?.toUpperCase() ?? 'U'}
                                            </div>
                                            <div>
                                                <p className="font-medium text-text-1">{m.user?.name ?? 'Unknown User'}</p>
                                                <p className="text-xs text-text-3">{m.user?.email}</p>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-4 py-3">
                                        <span className="inline-flex items-center h-6 px-2 rounded-md bg-bg-card-2 border border-border text-xs font-medium text-text-2 capitalize">
                                            {m.role}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-text-3">
                                        {m.joined_at ? new Date(m.joined_at).toLocaleDateString() : 'Unknown'}
                                    </td>
                                    <td className="px-4 py-3 text-right">
                                        <button className="text-brand text-xs font-medium hover:underline">
                                            Edit
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
