'use client';

import { useParams } from 'next/navigation';
import { useScan } from '@/lib/hooks/useScans';
import { getScanReportUrl } from '@/lib/api/scans';
import { SkeletonCard } from '@/components/ui/SkeletonCard';

export default function ScanReportPage() {
    const params = useParams();
    const scanId = params.id as string;
    const { data: scan, isLoading } = useScan(scanId);

    if (isLoading) return <SkeletonCard className="h-[600px]" />;
    if (!scan || scan.status !== 'completed') {
        return (
            <div className="text-center py-16">
                <p className="text-sm text-text-3">Report available after scan completes</p>
            </div>
        );
    }

    return (
        <div className="w-full h-[calc(100vh-10rem)] rounded-xl overflow-hidden border border-border">
            <iframe
                src={getScanReportUrl(scanId, 'html')}
                className="w-full h-full bg-white"
                title="CTO Report"
            />
        </div>
    );
}
