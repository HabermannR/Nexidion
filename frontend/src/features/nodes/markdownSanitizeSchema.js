import { defaultSchema } from 'rehype-sanitize';

export const markdownSanitizeSchema = {
    ...defaultSchema,
    attributes: {
        ...defaultSchema.attributes,
        // rehype-sanitize matches HAST property names, not serialized HTML names.
        span: [
            ...(defaultSchema.attributes?.span || []),
            'className',
            'dataUuid',
            'dataTarget',
            'dataDisplayText',
        ],
        img: [...(defaultSchema.attributes?.img || []), 'src', 'alt', 'title'],
    },
};
