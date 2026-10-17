import json

from django.core.management.base import BaseCommand, CommandError

from stations.utils import import_stations, write_geojson, StationImportError



class Command(BaseCommand):
    help = 'Import EV stations from a CSV file into station.geojson'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Path to the stations CSV file')
        parser.add_argument('--check-existing', action='store_true',
                            help='Skip stations whose station_id already exists')
        parser.add_argument('--json', action='store_true',
                            help='Print the summary as JSON')
        parser.add_argument('--output', type=str,
                            help='Export the imported stations to this GeoJSON file')

    def handle(self, *args, **options):
        try:
            summary, new_gdf = import_stations(
                options['csv_path'],
                check_existing=options['check_existing'],
            )

            if options['output']:
                write_geojson(new_gdf, options['output'])
                summary['output_file'] = options['output']

        except StationImportError as e:
            raise CommandError(str(e))

        if options['json']:
            self.stdout.write(json.dumps(summary, indent=2))
            return

        for row in summary['skipped']:
            self.stdout.write(self.style.WARNING(
                f"Skipped {row['station_id']} (row {row['row']}): {row['reason']}"
            ))

        self.stdout.write('')
        self.stdout.write(f"Total rows read : {summary['total_rows']}")
        self.stdout.write(self.style.SUCCESS(f"Rows written    : {summary['rows_written']}"))
        self.stdout.write(f"Rows skipped    : {summary['rows_skipped']}")

        if options['output']:
            self.stdout.write(self.style.SUCCESS(f"GeoJSON exported: {options['output']}"))
