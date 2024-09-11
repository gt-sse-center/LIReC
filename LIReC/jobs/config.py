configuration = {
    'jobs_to_run': [
        ('poly_pslq_v1', {
            'args': { 'degree': 2, 'order': 1, 'bulk': 1000, 'filters': {
                'global': { 'min_precision': 25 },
                'PcfCanonical': { 'count': 2, 'balanced_only': False },
                'Named': { 'count': 1, 'addons': ['pi*e'] }
                }
            },
            'run_async': False,
            'async_cores': 1
        })
    ]
}
