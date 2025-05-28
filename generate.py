#!/usr/bin/env python3

import argparse
import glob
import logging
import yaml

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('readme')

CONTAINER_TEMPLATE = '| [{}]({}) {} | {} | {} | {} |'
ENV_TEMPLATE = '| {} | {} | {} |'

notes = [
    (
        lambda s: s.get('network_mode', None) == 'service:tunnel',
        'All traffic is routed via tunnel VPN client container.'
    )
]

container_rows = [
    '| **Name** | **Description** | **Ports** | **Links** |',
    '|---|---|---|---|'
]

env_rows = [
    '| **Variable** | **Description** | **Example** |',
    '|---|---|---|'
]

mapped_tags = []


def mapped_tag(i):
    if i in mapped_tags:
        return mapped_tags.index(i) + 1
    else:
        mapped_tags.append(i)
        return len(mapped_tags)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog='generate-readme',
        description='Generate README.md from docker-compose files'
    )
    parser.add_argument(
        'files', nargs='*',
        help='docker-compose files to process'
    )
    parser.add_argument(
        '-t', '--template',
        help='README template file',
        default='README.tmpl.md'
    )
    parser.add_argument(
        '-o', '--output',
        help='output file name',
        default='README.md'
    )
    arguments = parser.parse_args()

    for file_name in sorted(arguments.files):
        with open(file_name, 'r', encoding="utf-8") as f:
            try:
                compose = yaml.safe_load(f)
                logger.info('processing compose file %s', file_name)
                for name, service in compose.get('services', {}).items():
                    labels = service.get('labels', {})

                    f.seek(0)
                    line_no = next(
                        num for num, line in enumerate(f, 1)
                        if f'container_name: {name}' in line
                    )

                    tags = ','.join([
                        str(mapped_tag(i)) for i, (predicate, _)
                        in enumerate(notes)
                        if predicate(service)
                    ])

                    container_rows.append(CONTAINER_TEMPLATE.format(
                        name,
                        f'{file_name}#L{line_no}',
                        f'<sup>{tags}</sup>' if tags else '',
                        labels.get('readme.description', ''),
                        ', '.join(map(
                            lambda p: f'`{p}`',
                            service.get('ports', [])
                        )),
                        ', '.join([
                            f'[{label}]({labels.get(f"readme.links.{i}")})'
                            for label, i in [
                                ('GitHub', 'github'),
                                ('GitLab', 'gitlab'),
                                ('Docker Hub', 'docker'),
                                ('Website', 'web')
                            ] if f'readme.links.{i}' in labels])
                    ))
                count = len(compose.get('services', {}))
                logger.info('processed %d services in %s', count, file_name)
            except yaml.YAMLError as e:
                logger.error('failed to parse yaml: %s', e)

    containers = '\n'.join(container_rows) + '\n\n'
    containers += '\n\n'.join(sorted([
        f'<sup>{str(tag + 1)}</sup>{notes[i][1]}'
        for tag, i in enumerate(mapped_tags)
    ]))

    for file_name in sorted(glob.glob('.env.*')):
        logger.info('processing variables in %s', file_name)
        comment = str()
        example = str()
        count = 0
        with open(file_name, 'r', encoding="utf-8") as f:
            for line in filter(lambda v: v.strip(), f.readlines()):
                if line.startswith('#'):
                    comment = line.strip('# ').strip()
                else:
                    value, example = line.split('=')
                    env_rows.append(ENV_TEMPLATE.format(
                        f'`{value}`', comment, f'`{example.strip()}`'
                    ))
                    count += 1
                    comment = str()
        logger.info('processed %d variables in %s', count, file_name)

    logger.info('reading README template')
    with open(arguments.template, 'r', encoding="utf-8") as f:
        readme = f.read().format(
            containers=containers,
            envs='\n'.join(env_rows) + '\n'
        )

        logger.info('writing new README')
        with open(arguments.output, 'w', encoding="utf-8") as f2:
            f2.write(readme)

    logger.info('done...')
