import { request } from './client';

export interface Org {
    id: string;
    name: string;
    slug: string;
    plan: 'free' | 'pro' | 'enterprise';
    created_at: string;
}

export interface Team {
    id: string;
    name: string;
    slug: string;
    member_count: number;
    created_at: string;
}

export interface TeamMember {
    id: string;
    user_id: string;
    role: string;
    joined_at: string;
    user: {
        name: string;
        email: string;
        avatar_url: string | null;
    } | null;
}

export function getOrganizations() {
    return request<{ organizations: Org[] }>('/api/v1/organizations');
}

export function getTeams(orgId: string) {
    return request<{ teams: Team[] }>(`/api/v1/organizations/${orgId}/teams`);
}

export function getTeamMembers(orgId: string, teamId: string) {
    return request<{ members: TeamMember[] }>(`/api/v1/organizations/${orgId}/teams/${teamId}/members`);
}

export function inviteMember(orgId: string, teamId: string, email: string, role: string = 'member') {
    return request(`/api/v1/organizations/${orgId}/teams/${teamId}/members`, {
        method: 'POST',
        body: JSON.stringify({ email, role }),
    });
}
