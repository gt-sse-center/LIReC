configuration = {
    'pool_size': 8,
    'jobs_to_run': [
        ('poly_pslq_v1', {
            'args': { 'degree': 5, 'order': 2, 'bulk': 1000, 'filters': {
                'global': { 'min_precision': 50 },
                'PcfCanonical': { 'count': 2, 'balanced_only': False },
                'Named': { 'count': 1, 'addons': ['pi*e'] }
                }
            },
            'run_async': True,
            'async_cores': 4
        }),
        ('poly_pslq_v1', {
            'args': { 'degree': 2, 'order': 2, 'bulk': 1000, 'filters': {
                'global': { 'min_precision': 30 },
                'PcfCanonical': { 'count': 2, 'balanced_only': False, 'addons': ['1/PCF[1,n]', '1/(PCF[2+2n,1-2n]-1)'] },
                'Named': { 'count': 2 }
                }
            },
            'run_async': True,
            'async_cores': 4
        })#,
        #'poly_pslq_v2', {
        #    'args': {
        #        'degree': 2, 'order': 1,
        #        'min_precision': 50, 'min_roi': 2,
        #        'testing_precision': 15, # replaces min_precision when fed to pslq
        #        'bulk': 10, # if testing lots of constants, can instead limit discovery to 'bulk' constants at a time until no relevant relation is found, then another 'bulk' constants are added
        #        #'filters': { # the existence of filters disables antirelation logging
        #        #    'PcfCanonical': { 'balanced_only': True }
        #        #}
        #    },
        #    'run_async': True,
        #    'iterations': 1
    ]
}