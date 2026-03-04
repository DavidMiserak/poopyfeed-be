# Code documentation

Inline documentation in this repo uses **Google-style** docstrings (Args, Returns, Raises, Example) for consistency with Sphinx and IDE tooling.

## Convention

- **Modules**: Top-level docstring describing the module’s role and main exports.
- **Classes**: Summary line, then Attributes/Example where useful.
- **Public functions/methods**: Summary, then Args, Returns, Raises as needed.
- **Private helpers** (`_name`): Short one-liner or Args/Returns when it clarifies behavior.

## Documentation update (March 2025)

The following files were updated for clearer or more complete docstrings:

 | File | Change |
 | --- | --- |
 | `django_project/middleware.py` | Added module docstring (APITiming, CSRFExempt, NoCacheAPI). |
 | `children/cache_utils.py` | Added Args/Returns to `_activities_to_cache`, `_activities_from_cache`. |
 | `django_project/cache.py` | Added Args/Returns to `SafeRedisCache.get`, `get_many`, `_handle_deserialize_error`, `_delete_key_safe`. |
 | `children/api_permissions.py` | Added Args/Returns to `HasChildAccess.has_object_permission`, `_get_child`. |
 | `django_project/db.py` | Expanded Args/Returns for `get_new_connection`, `close`. |
 | `feedings/constants.py` | Expanded module docstring and inline comments for constant groups. |

## Well-documented areas

These modules already had strong docstring coverage and were not changed:

- `children/tracking_api.py` – ViewSet and methods
- `children/models.py` – Child, ChildShare, ShareInvite and key methods
- `children/mixins.py` – Permission mixins and dispatch
- `children/datetime_utils.py` – All public functions
- `children/batch_api.py` – Serializers and BatchCreateView
- `analytics/cache.py` – Cache key helpers and invalidation
- `analytics/utils.py` – Aggregation helpers
- `django_project/throttles.py` – Throttle classes
- `django_project/health.py` – Health check views
- `django_project/db.py` – Module and class (only method docstrings were expanded)

## Running checks

- Docstrings are not enforced by the test suite. To audit coverage, search for public `def`/`class` without a following `"""` in application code (excluding tests and migrations).
